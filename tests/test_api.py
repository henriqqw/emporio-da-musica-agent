from datetime import date

import pytest
from fastapi.testclient import TestClient

from emporio.api import create_app
from emporio.config import PROJECT_ROOT, Settings
from emporio.service import build_chat_service
from tests.fakes import FakeClient, text_response

PHONE = "(67) 99654-7821"


@pytest.fixture
def llm():
    return FakeClient(text_response("Oi! Como posso ajudar?"), text_response("De nada!"))


@pytest.fixture
def api(llm, tmp_path):
    settings = Settings(
        model="claude-haiku-5-5",
        effort="low",
        reference_date=date(2026, 3, 25),
        session_ttl_minutes=30,
        data_dir=PROJECT_ROOT / "data",
        complaints_path=tmp_path / "complaints.jsonl",
    )
    return TestClient(create_app(build_chat_service(settings, llm)))


def test_chat_returns_the_reply(api, llm):
    response = api.post("/chat", json={"phone": PHONE, "text": "oi", "customer_name": "Ana"})
    assert response.status_code == 200
    assert response.json() == {"reply": "Oi! Como posso ajudar?"}
    assert "Ana" in llm.requests[0]["system"][1]["text"]


@pytest.mark.parametrize(
    "body",
    [
        {"phone": "123", "text": "oi"},  # invalid phone
        {"phone": PHONE, "text": ""},  # empty message
        {"phone": PHONE, "text": "x" * 2001},  # too long
        {"text": "oi"},  # missing phone
    ],
)
def test_invalid_input_is_rejected_before_the_llm(api, llm, body):
    assert api.post("/chat", json=body).status_code == 422
    assert llm.requests == []


def test_reset_starts_a_new_conversation(api, llm):
    api.post("/chat", json={"phone": PHONE, "text": "oi"})
    assert api.post("/chat/reset", json={"phone": PHONE}).status_code == 204
    api.post("/chat", json={"phone": PHONE, "text": "obrigado"})
    assert len(llm.requests[1]["messages"]) == 1


def test_index_and_health(api):
    assert "<title>" in api.get("/").text
    assert api.get("/health").json() == {"status": "ok"}
