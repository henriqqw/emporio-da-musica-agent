"""Settings read from the environment (.env is loaded if present)."""

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

STORE_TZ = ZoneInfo("America/Campo_Grande")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    model: str
    effort: str
    reference_date: date | None
    session_ttl_minutes: int
    data_dir: Path
    complaints_path: Path
    has_credentials: bool = False

    def now(self) -> datetime:
        """Current store time; the date part is REFERENCE_DATE when set."""
        real_now = datetime.now(STORE_TZ)
        if self.reference_date is None:
            return real_now
        return datetime.combine(self.reference_date, real_now.time(), tzinfo=STORE_TZ)

    def today(self) -> date:
        return self.now().date()


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    raw_date = os.getenv("REFERENCE_DATE", "").strip()
    return Settings(
        model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        effort=os.getenv("ANTHROPIC_EFFORT", "low"),
        reference_date=date.fromisoformat(raw_date) if raw_date else None,
        session_ttl_minutes=int(os.getenv("SESSION_TTL_MINUTES", "30")),
        data_dir=_project_path(os.getenv("DATA_DIR", "data")),
        complaints_path=_project_path(os.getenv("COMPLAINTS_PATH", "var/complaints.jsonl")),
        has_credentials=bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")),
    )


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path
