from datetime import date, datetime

import pytest

from emporio.config import PROJECT_ROOT, STORE_TZ, Settings
from emporio.service import IncomingMessage, build_chat_service
from tests.fakes import FakeClient, text_response, tool_response


def _settings(tmp_path):
    return Settings(
        model="claude-haiku-5-5",
        effort="low",
        reference_date=date(2026, 3, 25),
        session_ttl_minutes=30,
        data_dir=PROJECT_ROOT / "data",
        complaints_path=tmp_path / "complaints.jsonl",
    )


def _message(text, phone="+55 (67) 99654-7821", message_id="m1"):
    return IncomingMessage(channel="web", phone=phone, text=text, message_id=message_id)


def test_reply_is_sanitized_for_whatsapp(tmp_path):
    client = FakeClient(text_response("O **GD20** está disponível"))
    service = build_chat_service(_settings(tmp_path), client)
    assert service.handle(_message("oi")).text == "O *GD20* está disponível"


def test_history_is_kept_per_normalized_phone(tmp_path):
    client = FakeClient(text_response("Oi!"), text_response("Claro!"))
    service = build_chat_service(_settings(tmp_path), client)
    service.handle(_message("oi", phone="(67) 99654-7821"))
    service.handle(_message("e o preço?", phone="5567996547821"))

    second_request = client.requests[1]["messages"]
    assert [m["role"] for m in second_request] == ["user", "assistant", "user"]


def test_tools_receive_phone_and_message_id_from_the_channel(tmp_path):
    client = FakeClient(
        tool_response(
            "register_complaint",
            {"summary": "Entrega atrasada.", "category": "atraso_entrega", "order_id": 8},
        ),
        text_response("Registrei sua reclamação."),
    )
    service = build_chat_service(_settings(tmp_path), client)
    service.handle(_message("pode registrar", message_id="wamid.123"))

    record = (tmp_path / "complaints.jsonl").read_text(encoding="utf-8")
    assert '"phone": "67996547821"' in record
    assert '"message_id": "wamid.123"' in record
    assert '"order_id": 8' in record


def test_reference_date_drives_the_clock(tmp_path):
    client = FakeClient(text_response("Oi!"))
    service = build_chat_service(_settings(tmp_path), client)
    service.handle(_message("oi"))
    assert "25/03/2026" in client.requests[0]["system"][1]["text"]


def test_reset_starts_a_new_conversation(tmp_path):
    client = FakeClient(text_response("Oi!"), text_response("Oi de novo!"))
    service = build_chat_service(_settings(tmp_path), client)
    service.handle(_message("oi"))
    service.reset("67996547821")
    service.handle(_message("oi"))
    assert len(client.requests[1]["messages"]) == 1


def test_missing_api_key_fails_at_startup(tmp_path):
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_chat_service(_settings(tmp_path))


def test_store_timezone_is_used(tmp_path):
    settings = _settings(tmp_path)
    assert settings.now().tzinfo == STORE_TZ
    assert isinstance(settings.now(), datetime)
