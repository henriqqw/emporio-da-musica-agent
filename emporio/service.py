"""Channel-agnostic entry point (spec section 3, ADR-06).

Any channel - the web demo today, a WhatsApp webhook later - converts its payload
into an IncomingMessage and sends back OutgoingMessage.text. Nothing here knows
about HTTP.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import anthropic

from emporio.agent import Agent
from emporio.catalog import Catalog
from emporio.complaints import ComplaintStore
from emporio.config import Settings
from emporio.data import load_store_data
from emporio.orders import OrderService
from emporio.phone import normalize_phone
from emporio.sessions import SessionStore
from emporio.tools import Toolbox, ToolContext
from emporio.whatsapp_format import sanitize


@dataclass(frozen=True)
class IncomingMessage:
    channel: str  # "web" | "whatsapp"
    phone: str  # customer's phone = session identity
    text: str
    message_id: str  # unique per message (deduplication, complaint idempotency)
    customer_name: str | None = None  # e.g. WhatsApp profile name; only used to greet


@dataclass(frozen=True)
class OutgoingMessage:
    text: str  # already in WhatsApp format
    tools_used: tuple[str, ...] = ()  # for logs and transcripts; channels may ignore it


class ChatService:
    def __init__(self, agent: Agent, sessions: SessionStore, clock: Callable[[], datetime]):
        self._agent = agent
        self._sessions = sessions
        self._clock = clock

    def handle(self, message: IncomingMessage) -> OutgoingMessage:
        phone = normalize_phone(message.phone)
        now = self._clock()
        session = self._sessions.get(phone, now)
        with session.lock:  # one message at a time per customer
            session.messages.append({"role": "user", "content": message.text})
            reply = self._agent.respond(
                session.messages,
                ToolContext(phone=phone, message_id=message.message_id, now=now),
                message.customer_name,
            )
        return OutgoingMessage(text=sanitize(reply.text), tools_used=tuple(reply.tools_called))

    def reset(self, phone: str) -> None:
        self._sessions.reset(normalize_phone(phone))


def build_chat_service(
    settings: Settings, client: anthropic.Anthropic | None = None
) -> ChatService:
    """Wire the whole application from settings (composition root)."""
    if client is None and not settings.has_credentials:
        # Fail at startup, not on the first customer message.
        raise RuntimeError("ANTHROPIC_API_KEY is not set: copy .env.example to .env and fill it.")
    store = load_store_data(settings.data_dir)
    toolbox = Toolbox(Catalog(store), OrderService(store), ComplaintStore(settings.complaints_path))
    agent = Agent(client or anthropic.Anthropic(), toolbox, settings.model, settings.effort)
    sessions = SessionStore(ttl=timedelta(minutes=settings.session_ttl_minutes))
    return ChatService(agent, sessions, clock=settings.now)
