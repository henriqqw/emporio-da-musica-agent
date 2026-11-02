"""Agent loop driven by a scripted fake client: no network, no API key."""

import json
from datetime import datetime

import httpx
import openai
import pytest

from emporio.agent import FALLBACK_REPLY, MAX_TOOL_ROUNDS, Agent
from emporio.catalog import Catalog
from emporio.complaints import ComplaintStore
from emporio.config import STORE_TZ
from emporio.orders import OrderService
from emporio.tools import Toolbox, ToolContext
from tests.fakes import FakeClient, filtered_response, text_response, tool_response

CONTEXT = ToolContext(
    phone="67996547821", message_id="m1", now=datetime(2026, 3, 25, 14, 30, tzinfo=STORE_TZ)
)


@pytest.fixture
def toolbox(store, tmp_path):
    return Toolbox(Catalog(store), OrderService(store), ComplaintStore(tmp_path / "c.jsonl"))


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


def test_stops_after_max_tool_rounds(toolbox):
    looping = [tool_response("search_products", {"query": "violão"}, f"c{i}") for i in range(10)]
    client = FakeClient(*looping)
    reply = _agent(client, toolbox).respond(_history(), CONTEXT, None)
    assert reply.fallback is True
    assert reply.text == FALLBACK_REPLY
    assert len(client.requests) == MAX_TOOL_ROUNDS + 1


def test_content_filter_gives_fallback(toolbox):
    reply = _agent(FakeClient(filtered_response()), toolbox).respond(_history(), CONTEXT, None)
    assert reply.fallback is True


def test_empty_reply_gives_fallback(toolbox):
    reply = _agent(FakeClient(text_response("  ")), toolbox).respond(_history(), CONTEXT, None)
    assert reply.text == FALLBACK_REPLY


def test_api_error_gives_fallback(toolbox):
    error = openai.APIConnectionError(request=httpx.Request("POST", "https://api.test"))
    reply = _agent(FakeClient(error), toolbox).respond(_history(), CONTEXT, None)
    assert reply.text == FALLBACK_REPLY
