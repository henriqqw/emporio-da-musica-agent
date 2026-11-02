"""Agent loop driven by a scripted fake client: no network, no API key."""

import json
from datetime import datetime

import anthropic
import httpx2
import pytest

from emporio.agent import FALLBACK_REPLY, MAX_TOOL_ROUNDS, Agent
from emporio.catalog import Catalog
from emporio.complaints import ComplaintStore
from emporio.config import STORE_TZ
from emporio.orders import OrderService
from emporio.tools import Toolbox, ToolContext
from tests.fakes import FakeClient, refusal_response, text_response, tool_response

CONTEXT = ToolContext(
    phone="67996547821", message_id="m1", now=datetime(2026, 3, 25, 14, 30, tzinfo=STORE_TZ)
)


@pytest.fixture
def toolbox(store, tmp_path):
    return Toolbox(Catalog(store), OrderService(store), ComplaintStore(tmp_path / "c.jsonl"))


def _agent(client, toolbox):
    return Agent(client, toolbox, model="claude-haiku-5-5", effort="low")


def _history(text="Quanto custa o Takamine GD20?"):
    return [{"role": "user", "content": text}]


def test_plain_answer(toolbox):
    client = FakeClient(text_response("Oi! Como posso ajudar?"))
    reply = _agent(client, toolbox).respond(_history("oi"), CONTEXT, "Ana")
    assert reply.text == "Oi! Como posso ajudar?"
    assert reply.tools_called == []

    request = client.requests[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["output_config"] == {"effort": "low"}
    assert "Ana" in request["system"][1]["text"]


def test_tool_round_trip_appends_to_history(toolbox):
    client = FakeClient(
        tool_response("search_products", {"query": "takamine gd20"}),
        text_response("O GD20 sai por R$ 2.199,00."),
    )
    history = _history()
    reply = _agent(client, toolbox).respond(history, CONTEXT, None)

    assert reply.text == "O GD20 sai por R$ 2.199,00."
    assert reply.tools_called == ["search_products"]
    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant", "user", "assistant"]

    tool_result = history[2]["content"][0]
    assert tool_result["tool_use_id"] == "t1"
    assert "is_error" not in tool_result
    assert json.loads(tool_result["content"])["products"][0]["pix_price"] == 2089.05


def test_invalid_tool_call_goes_back_as_error(toolbox):
    client = FakeClient(
        tool_response("search_products", {}),
        text_response("Me conta qual instrumento você procura?"),
    )
    history = _history("tem coisa barata?")
    _agent(client, toolbox).respond(history, CONTEXT, None)
    tool_result = history[2]["content"][0]
    assert tool_result["is_error"] is True


def test_stops_after_max_tool_rounds(toolbox):
    looping = [tool_response("search_products", {"query": "violão"}, f"t{i}") for i in range(10)]
    client = FakeClient(*looping)
    reply = _agent(client, toolbox).respond(_history(), CONTEXT, None)
    assert reply.fallback is True
    assert reply.text == FALLBACK_REPLY
    assert len(client.requests) == MAX_TOOL_ROUNDS + 1


def test_refusal_gives_fallback(toolbox):
    reply = _agent(FakeClient(refusal_response()), toolbox).respond(_history(), CONTEXT, None)
    assert reply.fallback is True


def test_api_error_gives_fallback(toolbox):
    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.test"))
    reply = _agent(FakeClient(error), toolbox).respond(_history(), CONTEXT, None)
    assert reply.text == FALLBACK_REPLY
