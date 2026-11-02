import json
from datetime import datetime

import pytest

from emporio.complaints import ComplaintStore, response_deadline
from emporio.config import STORE_TZ

WEDNESDAY = datetime(2026, 3, 25, 14, 30, tzinfo=STORE_TZ)


@pytest.fixture
def complaints(tmp_path):
    return ComplaintStore(tmp_path / "var" / "complaints.jsonl")


def _register(complaints, message_id="m1", **overrides):
    fields = {
        "phone": "67996547821",
        "message_id": message_id,
        "category": "atraso_entrega",
        "summary": "Pedido 8 com entrega atrasada desde 28/02.",
        "order_id": 8,
        "now": WEDNESDAY,
    }
    return complaints.register(**(fields | overrides))


def test_registers_with_protocol_and_deadline(complaints, tmp_path):
    # A16: Wednesday 14:30 -> Thursday 14:30
    complaint = _register(complaints)
    assert complaint.protocol == "REC-20260325-0001"
    assert complaint.response_deadline == "2026-03-26T14:30-04:00"

    lines = (tmp_path / "var" / "complaints.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["order_id"] == 8


def test_protocol_sequence_per_day(complaints):
    assert _register(complaints, "m1").protocol.endswith("-0001")
    assert _register(complaints, "m2").protocol.endswith("-0002")
    next_day = datetime(2026, 3, 26, 9, 0, tzinfo=STORE_TZ)
    assert _register(complaints, "m3", now=next_day).protocol == "REC-20260326-0001"


def test_same_message_id_never_creates_two_complaints(complaints, tmp_path):
    first = _register(complaints, "m1")
    again = _register(complaints, "m1", summary="outro texto")
    assert again == first
    lines = (tmp_path / "var" / "complaints.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


@pytest.mark.parametrize(
    ("start", "deadline"),
    [
        (datetime(2026, 3, 25, 14, 30), datetime(2026, 3, 26, 14, 30)),  # Wed -> Thu
        (datetime(2026, 3, 27, 15, 0), datetime(2026, 3, 30, 15, 0)),  # Fri -> Mon
        (datetime(2026, 3, 28, 10, 0), datetime(2026, 3, 31, 0, 0)),  # Sat -> Tue 00:00
        (datetime(2026, 3, 29, 23, 0), datetime(2026, 3, 31, 0, 0)),  # Sun -> Tue 00:00
    ],
)
def test_deadline_skips_weekends(start, deadline):
    tz = {"tzinfo": STORE_TZ}
    assert response_deadline(start.replace(**tz)) == deadline.replace(**tz)


@pytest.mark.parametrize(
    "overrides",
    [{"category": "inexistente"}, {"summary": "   "}, {"summary": "x" * 501}],
)
def test_rejects_invalid_input(complaints, overrides):
    with pytest.raises(ValueError):
        _register(complaints, **overrides)
