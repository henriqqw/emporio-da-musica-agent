"""Complaint registration: the agent's single write (spec 5.3, rules R-CMP-*).

Records go to a JSONL file through ComplaintStore. Sending tickets to a real
helpdesk instead means replacing that one class.
"""

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

CATEGORIES = ("atraso_entrega", "produto_com_defeito", "atendimento", "cobranca", "outro")
RESPONSE_BUSINESS_HOURS = 24  # R-TONE-4
MAX_SUMMARY_LENGTH = 500


@dataclass(frozen=True)
class Complaint:
    protocol: str
    message_id: str
    phone: str
    category: str
    summary: str
    order_id: int | None
    created_at: str  # ISO 8601, store time zone
    response_deadline: str


class ComplaintStore:
    """Append-only JSONL file. A lock keeps protocol numbers unique within the process."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def register(
        self,
        *,
        phone: str,
        message_id: str,
        category: str,
        summary: str,
        order_id: int | None,
        now: datetime,
    ) -> Complaint:
        """Store a complaint, or return the one already stored for this message (R-CMP-5).

        A message is identified by phone + message_id: in the web channel the id comes
        from the client, so the id alone could match another customer's complaint.
        """
        if category not in CATEGORIES:
            raise ValueError(f"unknown category: {category}")
        summary = summary.strip()
        if not summary or len(summary) > MAX_SUMMARY_LENGTH:
            raise ValueError(f"summary must have 1-{MAX_SUMMARY_LENGTH} characters")

        with self._lock:
            existing = self._load()
            for complaint in existing:
                if (complaint.phone, complaint.message_id) == (phone, message_id):
                    return complaint

            complaint = Complaint(
                protocol=_protocol(now, existing),
                message_id=message_id,
                phone=phone,
                category=category,
                summary=summary,
                order_id=order_id,
                created_at=now.isoformat(timespec="minutes"),
                response_deadline=response_deadline(now).isoformat(timespec="minutes"),
            )
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(asdict(complaint), ensure_ascii=False) + "\n")
            return complaint

    def _load(self) -> list[Complaint]:
        if not self._path.exists():
            return []
        with self._path.open(encoding="utf-8") as file:
            return [Complaint(**json.loads(line)) for line in file if line.strip()]


def response_deadline(start: datetime) -> datetime:
    """24 hours counted only on Monday-Friday (R-CMP-4); holidays are not known.

    Friday 15:00 -> Monday 15:00; Saturday 10:00 -> Tuesday 00:00.
    """
    remaining = timedelta(hours=RESPONSE_BUSINESS_HOURS)
    cursor = start
    while remaining > timedelta(0):
        midnight = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if cursor.weekday() >= 5:  # Saturday or Sunday: skip the rest of the day
            cursor = midnight
            continue
        step = min(remaining, midnight - cursor)
        cursor += step
        remaining -= step
    return cursor


def _protocol(now: datetime, existing: list[Complaint]) -> str:
    """REC-YYYYMMDD-NNNN, numbered per day (R-CMP-3)."""
    day = now.strftime("%Y%m%d")
    prefix = f"REC-{day}-"
    count = sum(1 for c in existing if c.protocol.startswith(prefix))
    return f"{prefix}{count + 1:04d}"
