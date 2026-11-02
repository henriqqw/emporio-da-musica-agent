"""Demo web channel (spec section 3): POST /chat plus a static chat page.

This is a channel adapter only: it validates HTTP input, maps it to an
IncomingMessage and returns the reply. A WhatsApp webhook would be a sibling
module doing the same with the provider's payload.
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from emporio.config import PROJECT_ROOT, load_settings
from emporio.phone import is_valid_phone, normalize_phone
from emporio.rate_limit import RateLimiter
from emporio.service import ChatService, IncomingMessage, build_chat_service

STATIC_DIR = PROJECT_ROOT / "static"
INDEX_HTML = STATIC_DIR / "index.html"
# Defence in depth behind the page's HTML escaping: only the page's own files may run
# or style it, it may only call this API, and no other site may frame it (clickjacking).
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
# FastAPI's /docs and /redoc load Swagger/ReDoc from a CDN and use an inline script.
# They are developer pages that never render customer content, so they get their own,
# looser policy; the chat page and the API keep the strict one.
DOCS_PATHS = ("/docs", "/redoc")
DOCS_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
    "font-src https://fonts.gstatic.com; worker-src blob:; connect-src 'self'; "
    "frame-ancestors 'none'"
)
# Per minute. Generous for a person typing; stops a script brute-forcing the e-mail of
# a known phone or burning the LLM quota. Checked before the agent, so a rejected
# message costs no LLM call.
MESSAGES_PER_PHONE = 10
MESSAGES_PER_IP = 30
TOO_MANY_MESSAGES = "Muitas mensagens em pouco tempo. Aguarde um minuto e tente de novo."

API_DESCRIPTION = (
    "Customer-service agent for Empório da Música. This demo channel stands in for "
    "WhatsApp: the phone number identifies the customer. See the README to try it."
)
TAGS = [
    {"name": "chat", "description": "Talk to the agent as a customer would on WhatsApp."},
    {"name": "ops", "description": "Operational endpoints."},
]


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable reason, in Portuguese.")


class PhoneField(BaseModel):
    phone: str = Field(
        description=(
            "The customer's WhatsApp number (DDD + number, with or without +55 and "
            "punctuation). It identifies the session and the customer; it is never taken "
            "from what the customer types."
        ),
        examples=["(67) 99654-7821"],
    )

    @field_validator("phone")
    @classmethod
    def _valid_phone(cls, value: str) -> str:
        if not is_valid_phone(value):
            raise ValueError("telefone inválido: informe DDD + número")
        return value


class ChatRequest(PhoneField):
    text: str = Field(
        min_length=1,
        max_length=2000,
        description="What the customer wrote.",
        examples=["Quanto custa o Takamine GD20?"],
    )
    message_id: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Unique id of the message (on WhatsApp, the provider's message id). Optional "
            "here: generated when omitted. The same id never opens two complaints."
        ),
        examples=["wamid.HBgMNTU2Nzk5NjU0NzgyMQ"],
    )
    customer_name: str | None = Field(
        default=None,
        max_length=60,
        description="WhatsApp profile name, used only to greet; sanitized before use.",
        examples=["Ana Carolina"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "phone": "(67) 99654-7821",
                    "text": "Quanto custa o Takamine GD20?",
                    "customer_name": "Ana Carolina",
                }
            ]
        }
    )


class ChatResponse(BaseModel):
    reply: str = Field(
        description=(
            "The agent's answer, in WhatsApp format. If the LLM provider fails, a polite "
            "apology with the store's contacts (still HTTP 200)."
        ),
        examples=[
            "O *Takamine GD20 Dreadnought Natural* custa R$ 2.199,00, ou R$ 2.089,05 no PIX, "
            "e você pode parcelar em até 12x de R$ 183,25 sem juros."
        ],
    )


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


RATE_LIMITED: dict[int | str, dict[str, Any]] = {
    429: {
        "model": ErrorResponse,
        "description": (
            f"Too many messages: over {MESSAGES_PER_PHONE} per minute for this phone or "
            f"{MESSAGES_PER_IP} for this IP. The LLM was not called."
        ),
        "content": {"application/json": {"example": {"detail": TOO_MANY_MESSAGES}}},
    }
}


def create_app(
    service: ChatService | None = None, clock: Callable[[], float] = time.monotonic
) -> FastAPI:
    """App factory; tests inject a service built on a fake LLM client and a clock."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    chat = service or build_chat_service(load_settings())
    app = FastAPI(
        title="Empório da Música — assistente virtual",
        version="1.0.0",
        description=API_DESCRIPTION,
        openapi_tags=TAGS,
    )
    per_phone = RateLimiter(MESSAGES_PER_PHONE, window_seconds=60, clock=clock)
    per_ip = RateLimiter(MESSAGES_PER_IP, window_seconds=60, clock=clock)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if request.url.path in DOCS_PATHS:
            response.headers["Content-Security-Policy"] = DOCS_CSP
        return response

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(INDEX_HTML)

    @app.get("/health", tags=["ops"], summary="Liveness check")
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post(
        "/chat",
        tags=["chat"],
        summary="Send a customer message and get the agent's reply",
        description=(
            "One turn of the conversation. The agent may look up the catalog, an order "
            "(only after the customer gives the registered e-mail) or register a complaint "
            "before answering. Prices, dates and protocols come from code, not from the "
            "model."
        ),
        responses=RATE_LIMITED,
    )
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

    @app.post(
        "/chat/reset",
        status_code=204,
        tags=["chat"],
        summary="Start a new conversation for a phone",
        description="Forgets the conversation history of this phone (demo convenience).",
    )
    def reset_chat(request: PhoneField) -> None:
        chat.reset(request.phone)

    return app
