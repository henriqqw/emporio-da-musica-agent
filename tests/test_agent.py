"""Agent loop driven by a scripted fake client: no network, no API key."""

import json

import httpx
import openai
import pytest

from emporio.agent import (
    EMPTY_REPLY,
    FALLBACK_REPLY,
    FILTERED,
    MALFORMED_RESPONSE,
    MAX_TOOL_ROUNDS,
    PROVIDER_ERROR,
    TOOL_LIMIT,
    Agent,
)
from emporio.tools import ToolContext
from tests.constants import ANA_PHONE, STORE_NOW
from tests.fakes import FakeClient, filtered_response, text_response, tool_response

CONTEXT = ToolContext(phone=ANA_PHONE, message_id="m1", now=STORE_NOW)


def _agent(client, toolbox, reasoning_effort=None):
    return Agent(client, toolbox, model="fake-model", reasoning_effort=reasoning_effort)


def _history(text="Quanto custa o Takamine GD20?"):
    return [{"role": "user", "content": text}]


def test_plain_answer(toolbox):
    client = FakeClient(text_response("Oi! Como posso ajudar?"))
    reply = _agent(client, toolbox).respond(_history("oi"), CONTEXT, "Ana")
    assert reply.text == "Oi! Como posso ajudar?"
    assert reply.tools_called == []

    request = client.requests[0]
    assert request["model"] == "fake-model"
    assert "reasoning_effort" not in request  # only sent when configured
    system, user = request["messages"]
    assert system["role"] == "system"
    assert "Ana" in system["content"]
    assert "Categorias com produtos disponíveis hoje: Guitarras" in system["content"]
    assert "Sopro" not in system["content"].split("# Contexto desta conversa")[1]
    assert user == {"role": "user", "content": "oi"}


def test_reasoning_effort_is_sent_when_configured(toolbox):
    client = FakeClient(text_response("Oi!"))
    _agent(client, toolbox, reasoning_effort="low").respond(_history("oi"), CONTEXT, None)
    assert client.requests[0]["reasoning_effort"] == "low"


def test_tool_round_trip_appends_to_history(toolbox):
    client = FakeClient(
        tool_response("search_products", {"query": "takamine gd20"}),
        text_response("O GD20 sai por R$ 2.199,00."),
    )
    history = _history()
    reply = _agent(client, toolbox).respond(history, CONTEXT, None)

    assert reply.text == "O GD20 sai por R$ 2.199,00."
    assert reply.tools_called == ["search_products"]
    assert [m["role"] for m in history] == ["user", "assistant", "tool", "assistant"]

    assistant_call = history[1]["tool_calls"][0]
    assert assistant_call["function"]["name"] == "search_products"
    tool_message = history[2]
    assert tool_message["tool_call_id"] == "call_1"
    assert json.loads(tool_message["content"])["products"][0]["pix_price"] == "R$ 2.089,05"

    # the system prompt is never stored in the session history
    assert all(m["role"] != "system" for m in history)


@pytest.mark.parametrize(
    "arguments",
    [{}, "{not json"],  # fails validation / is not JSON
)
def test_invalid_tool_call_goes_back_as_error(toolbox, arguments):
    client = FakeClient(
        tool_response("search_products", arguments),
        text_response("Me conta qual instrumento você procura?"),
    )
    history = _history("tem coisa barata?")
    reply = _agent(client, toolbox).respond(history, CONTEXT, None)
    assert history[2]["content"].startswith("ERRO:")
    assert reply.text == "Me conta qual instrumento você procura?"


def test_stops_after_max_tool_rounds_without_running_the_extra_call(toolbox, complaints_path):
    searches = [tool_response("search_products", {"query": "violão"}, f"c{i}") for i in range(5)]
    # the model asks for a write after the round limit: it must not happen silently
    complaint = tool_response(
        "register_complaint", {"summary": "Atraso.", "category": "atraso_entrega"}, "c5"
    )
    client = FakeClient(*searches, complaint)
    history = _history()
    reply = _agent(client, toolbox).respond(history, CONTEXT, None)

    assert reply.fallback_reason == TOOL_LIMIT
    assert reply.text == FALLBACK_REPLY
    assert len(client.requests) == MAX_TOOL_ROUNDS + 1
    assert reply.tools_called == ["search_products"] * MAX_TOOL_ROUNDS
    assert not complaints_path.exists()
    # the unexecuted call is not left in the history either
    assert history[-1]["role"] == "tool"


def test_content_filter_gives_fallback(toolbox):
    reply = _agent(FakeClient(filtered_response()), toolbox).respond(_history(), CONTEXT, None)
    assert (reply.text, reply.fallback_reason) == (FALLBACK_REPLY, FILTERED)


def test_model_refusal_gives_fallback(toolbox):
    refusal = text_response("")
    refusal.choices[0].message.refusal = "Não posso ajudar com isso."
    reply = _agent(FakeClient(refusal), toolbox).respond(_history(), CONTEXT, None)
    assert reply.fallback_reason == FILTERED


def test_empty_reply_gives_fallback_and_is_not_stored(toolbox):
    history = _history()
    reply = _agent(FakeClient(text_response("  ")), toolbox).respond(history, CONTEXT, None)
    assert (reply.text, reply.fallback_reason) == (FALLBACK_REPLY, EMPTY_REPLY)
    # an empty assistant turn could make the provider reject the rest of the session
    assert history == _history()


def test_api_error_gives_fallback(toolbox):
    error = openai.APIConnectionError(request=httpx.Request("POST", "https://api.test"))
    reply = _agent(FakeClient(error), toolbox).respond(_history(), CONTEXT, None)
    assert (reply.text, reply.fallback_reason) == (FALLBACK_REPLY, PROVIDER_ERROR)


def test_malformed_response_gives_fallback_not_an_exception(toolbox):
    no_choices = text_response("oi")
    no_choices.choices = []  # some compatible providers do this
    reply = _agent(FakeClient(no_choices), toolbox).respond(_history(), CONTEXT, None)
    assert (reply.text, reply.fallback_reason) == (FALLBACK_REPLY, MALFORMED_RESPONSE)


def test_crashing_tool_goes_back_as_error_and_the_turn_continues(toolbox, monkeypatch):
    def crash(*_):
        raise RuntimeError("bug")

    monkeypatch.setattr(toolbox, "run", crash)
    client = FakeClient(
        tool_response("search_products", {"query": "gd20"}),
        text_response("Tive um problema na consulta, pode repetir?"),
    )
    history = _history()
    reply = _agent(client, toolbox).respond(history, CONTEXT, None)
    assert history[2]["content"] == "ERRO: falha interna ao executar a ferramenta."
    assert reply.fallback_reason is None


def test_parallel_tool_calls_all_get_a_result(toolbox):
    first = tool_response("search_products", {"query": "gd20"}, "a")
    second = tool_response("search_products", {"query": "c40"}, "b")
    first.choices[0].message.tool_calls += second.choices[0].message.tool_calls
    client = FakeClient(first, text_response("Os dois estão disponíveis."))
    history = _history()
    _agent(client, toolbox).respond(history, CONTEXT, None)
    assert [m.get("tool_call_id") for m in history if m["role"] == "tool"] == ["a", "b"]
