"""Demo web channel (spec section 3): POST /chat plus a static chat page.

This is a channel adapter only: it validates HTTP input, maps it to an
IncomingMessage and returns the reply. A WhatsApp webhook would be a sibling
module doing the same with the provider's payload.
"""

import logging
import time
import uuid
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from emporio.config import PROJECT_ROOT, load_settings
from emporio.phone import is_valid_phone, normalize_phone
from emporio.rate_limit import RateLimiter
from emporio.service import ChatService, IncomingMessage, build_chat_service

INDEX_HTML = PROJECT_ROOT / "static" / "index.html"
# Per minute. Generous for a person typing; stops a script brute-forcing the e-mail of
# a known phone or burning the LLM quota. Checked before the agent, so a rejected
# message costs no LLM call.
MESSAGES_PER_PHONE = 10
MESSAGES_PER_IP = 30
TOO_MANY_MESSAGES = "Muitas mensagens em pouco tempo. Aguarde um minuto e tente de novo."


class PhoneField(BaseModel):
    phone: str = Field(examples=["(67) 99654-7821"])

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str) -> str:
        if not is_valid_phone(value):
            raise ValueError("telefone inválido: informe DDD + número")
        return value


class ChatRequest(PhoneField):
    text: str = Field(min_length=1, max_length=2000)
    message_id: str | None = Field(default=None, max_length=200)
    customer_name: str | None = Field(default=None, max_length=60)


class ChatResponse(BaseModel):
    reply: str


def create_app(
    service: ChatService | None = None, clock: Callable[[], float] = time.monotonic
) -> FastAPI:
    """App factory; tests inject a service built on a fake LLM client and a clock."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    chat = service or build_chat_service(load_settings())
    app = FastAPI(title="Empório da Música — assistente virtual")
    per_phone = RateLimiter(MESSAGES_PER_PHONE, window_seconds=60, clock=clock)
    per_ip = RateLimiter(MESSAGES_PER_IP, window_seconds=60, clock=clock)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(INDEX_HTML)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat")
    def post_chat(request: ChatRequest, http: Request) -> ChatResponse:
        client_ip = http.client.host if http.client else "unknown"
        if not per_ip.allow(client_ip) or not per_phone.allow(normalize_phone(request.phone)):
            raise HTTPException(status_code=429, detail=TOO_MANY_MESSAGES)
        message = IncomingMessage(
            channel="web",
            phone=request.phone,
            text=request.text,
            message_id=request.message_id or str(uuid.uuid4()),
            customer_name=(request.customer_name or "").strip() or None,
        )
        return ChatResponse(reply=chat.handle(message).text)

    @app.post("/chat/reset", status_code=204)
    def reset_chat(request: PhoneField) -> None:
        chat.reset(request.phone)

    return app
