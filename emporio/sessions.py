"""In-memory conversation history per customer phone (spec section 4, ADR-08).

History is append-only, as the API requires for tool-use blocks; a session that
has been idle longer than the TTL starts over instead of being trimmed.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class Session:
    phone: str
    last_activity: datetime
    messages: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


class SessionStore:
    def __init__(self, ttl: timedelta) -> None:
        self._ttl = ttl
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get(self, phone: str, now: datetime) -> Session:
        """The customer's current session, or a fresh one if missing or expired."""
        with self._lock:
            session = self._sessions.get(phone)
            if session is None or now - session.last_activity > self._ttl:
                session = Session(phone=phone, last_activity=now)
                self._sessions[phone] = session
            session.last_activity = now
            return session

    def reset(self, phone: str) -> None:
        with self._lock:
            self._sessions.pop(phone, None)
