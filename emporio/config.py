"""Settings read from the environment (.env is loaded if present)."""

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

STORE_TZ = ZoneInfo("America/Campo_Grande")
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default provider: Gemini's OpenAI-compatible endpoint, free tier (ADR-03, ADR-13).
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-flash-lite-latest"


@dataclass(frozen=True)
class Settings:
    model: str
    reference_date: date | None
    session_ttl_minutes: int
    data_dir: Path
    complaints_path: Path
    llm_base_url: str = DEFAULT_BASE_URL
    llm_api_key: str = field(default="", repr=False)  # never printed in logs or errors
    reasoning_effort: str | None = None

    def now(self) -> datetime:
        """Current store time; the date part is REFERENCE_DATE when set."""
        real_now = datetime.now(STORE_TZ)
        if self.reference_date is None:
            return real_now
        return datetime.combine(self.reference_date, real_now.time(), tzinfo=STORE_TZ)


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    raw_date = os.getenv("REFERENCE_DATE", "").strip()
    return Settings(
        model=os.getenv("LLM_MODEL") or DEFAULT_MODEL,
        reference_date=date.fromisoformat(raw_date) if raw_date else None,
        session_ttl_minutes=_positive_int("SESSION_TTL_MINUTES", default=30),
        data_dir=_project_path(os.getenv("DATA_DIR", "data")),
        complaints_path=_project_path(os.getenv("COMPLAINTS_PATH", "var/complaints.jsonl")),
        llm_base_url=os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL,
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        reasoning_effort=os.getenv("LLM_REASONING_EFFORT") or None,
    )


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    if not raw.isdigit() or int(raw) == 0:
        raise ValueError(f"{name} must be a positive whole number, got {raw!r}")
    return int(raw)


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path
