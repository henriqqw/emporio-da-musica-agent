import pytest

from emporio.config import STORE_TZ
from emporio.service import IncomingMessage, build_chat_service
from tests.constants import REFERENCE_DATE
from tests.fakes import FakeClient, text_response, tool_response


def _message(text, phone="+55 (67) 99654-7821", message_id="m1"):
    return IncomingMessage(channel="web", phone=phone, text=text, message_id=message_id)


def test_reply_is_sanitized_for_whatsapp(settings):
    client = FakeClient(text_response("O **GD20** está disponível"))
    service = build_chat_service(settings, client)
    reply = service.handle(_message("oi"))
    assert reply.text == "O *GD20* está disponível"
    assert reply.fallback_reason is None


def test_fallback_reason_reaches_the_channel(settings):
    service = build_chat_service(settings, FakeClient(text_response("")))
    assert service.handle(_message("oi")).fallback_reason == "empty_reply"


def test_history_is_kept_per_normalized_phone(settings):
    client = FakeClient(text_response("Oi!"), text_response("Claro!"))
    service = build_chat_service(settings, client)
    service.handle(_message("oi", phone="(67) 99654-7821"))
    service.handle(_message("e o preço?", phone="5567996547821"))

    second_request = client.requests[1]["messages"]
    assert [m["role"] for m in second_request] == ["system", "user", "assistant", "user"]


def test_tools_receive_phone_and_message_id_from_the_channel(settings, complaints_path):
    client = FakeClient(
        tool_response(
            "register_complaint",
            {"summary": "Entrega atrasada.", "category": "atraso_entrega", "order_id": 8},
        ),
        text_response("Registrei sua reclamação."),
    )
    service = build_chat_service(settings, client)
    reply = service.handle(_message("pode registrar", message_id="wamid.123"))
    assert reply.tools_used == ("register_complaint",)

    record = complaints_path.read_text(encoding="utf-8")
    assert '"phone": "67996547821"' in record
    assert '"message_id": "wamid.123"' in record
    assert '"order_id": 8' in record


def test_reference_date_drives_the_clock(settings):
    client = FakeClient(text_response("Oi!"))
    service = build_chat_service(settings, client)
    service.handle(_message("oi"))
    assert "25/03/2026" in client.requests[0]["messages"][0]["content"]


def test_reset_starts_a_new_conversation(settings):
    client = FakeClient(text_response("Oi!"), text_response("Oi de novo!"))
    service = build_chat_service(settings, client)
    service.handle(_message("oi"))
    service.reset("67996547821")
    service.handle(_message("oi"))
    assert len(client.requests[1]["messages"]) == 2  # system + the new message


def test_missing_api_key_fails_at_startup(settings):
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        build_chat_service(settings)


def test_clock_uses_the_reference_date_in_the_store_time_zone(settings):
    now = settings.now()
    assert (now.date(), now.tzinfo) == (REFERENCE_DATE, STORE_TZ)
