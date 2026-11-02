import pytest
from fastapi.testclient import TestClient

from emporio.api import MESSAGES_PER_IP, MESSAGES_PER_PHONE, create_app
from emporio.service import build_chat_service
from tests.constants import ANA_PHONE as PHONE
from tests.fakes import FakeClient, FakeClock, text_response


@pytest.fixture
def llm():
    return FakeClient(text_response("Oi! Como posso ajudar?"), text_response("De nada!"))


@pytest.fixture
def api(llm, settings):
    return TestClient(create_app(build_chat_service(settings, llm)))


def test_chat_returns_the_reply(api, llm):
    response = api.post("/chat", json={"phone": PHONE, "text": "oi", "customer_name": "Ana"})
    assert response.status_code == 200
    assert response.json() == {"reply": "Oi! Como posso ajudar?"}
    assert "Ana" in llm.requests[0]["messages"][0]["content"]


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
    assert len(llm.requests[1]["messages"]) == 2  # system + the new message


def test_index_and_health(api):
    assert "<title>" in api.get("/").text
    assert api.get("/health").json() == {"status": "ok"}


def test_rate_limit_per_phone_blocks_before_the_llm(settings):
    llm = FakeClient(*[text_response("ok") for _ in range(MESSAGES_PER_PHONE)])
    client = TestClient(create_app(build_chat_service(settings, llm)))
    for _ in range(MESSAGES_PER_PHONE):
        assert client.post("/chat", json={"phone": PHONE, "text": "oi"}).status_code == 200

    blocked = client.post("/chat", json={"phone": PHONE, "text": "oi"})
    assert blocked.status_code == 429
    assert "Aguarde um minuto" in blocked.json()["detail"]
    assert len(llm.requests) == MESSAGES_PER_PHONE  # the blocked message cost no LLM call
    # another phone is not affected
    other = client.post("/chat", json={"phone": "(67) 98432-1098", "text": "oi"})
    assert other.status_code != 429


def test_rate_limit_per_ip_across_phones(settings):
    # a script changing the phone on every try is still limited by its address
    llm = FakeClient(*[text_response("ok") for _ in range(MESSAGES_PER_IP)])
    client = TestClient(create_app(build_chat_service(settings, llm)))
    phones = [f"(67) 99{n:03d}-0000" for n in range(MESSAGES_PER_IP + 1)]
    codes = [client.post("/chat", json={"phone": p, "text": "oi"}).status_code for p in phones]
    assert codes[:MESSAGES_PER_IP] == [200] * MESSAGES_PER_IP
    assert codes[-1] == 429


def test_rate_limit_window_resets(settings):
    clock = FakeClock()
    llm = FakeClient(*[text_response("ok") for _ in range(MESSAGES_PER_PHONE + 1)])
    client = TestClient(create_app(build_chat_service(settings, llm), clock=clock))
    for _ in range(MESSAGES_PER_PHONE):
        client.post("/chat", json={"phone": PHONE, "text": "oi"})
    assert client.post("/chat", json={"phone": PHONE, "text": "oi"}).status_code == 429
    clock.now += 60
    assert client.post("/chat", json={"phone": PHONE, "text": "oi"}).status_code == 200


@pytest.mark.parametrize("path", ["/", "/static/app.js", "/health"])
def test_security_headers_on_every_response(api, path):
    headers = api.get(path).headers
    csp = headers["content-security-policy"]
    assert "script-src 'self'" in csp  # no inline or third-party scripts
    assert "frame-ancestors 'none'" in csp
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"


def test_page_has_no_inline_script_or_style(api):
    # the CSP blocks inline code, so the page must load everything from files
    page = api.get("/").text
    assert "<script>" not in page and "<style>" not in page
    assert api.get("/static/app.js").status_code == 200
    assert api.get("/static/app.css").status_code == 200


def test_api_docs_get_a_policy_that_lets_swagger_load(api):
    # /docs loads Swagger from a CDN with an inline script: the strict policy blocked it
    response = api.get("/docs")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp
    assert "frame-ancestors 'none'" in csp
    # the chat page keeps the strict one
    assert "cdn.jsdelivr.net" not in api.get("/").headers["content-security-policy"]


def test_openapi_documents_the_contract(api):
    spec = api.get("/openapi.json").json()
    chat = spec["paths"]["/chat"]["post"]
    assert chat["tags"] == ["chat"]
    assert {"200", "422", "429"} <= set(chat["responses"])  # the rate limit is documented
    body = spec["components"]["schemas"]["ChatRequest"]
    assert all(field.get("description") for field in body["properties"].values())
    assert spec["info"]["version"] == "1.0.0"
    assert "/" not in spec["paths"]  # the chat page is not an API endpoint
