from datetime import datetime

import pytest

from emporio.config import STORE_TZ
from emporio.store_hours import is_open, next_opening


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    """March 2026: the 23rd is a Monday."""
    return datetime(2026, 3, day, hour, minute, tzinfo=STORE_TZ)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (_at(25, 8, 59), False),  # Wednesday before opening
        (_at(25, 9), True),
        (_at(25, 17, 59), True),
        (_at(25, 18), False),  # closes at 18:00
        (_at(28, 12, 59), True),  # Saturday until 13:00
        (_at(28, 13), False),
        (_at(29, 11), False),  # Sunday closed
    ],
)
def test_is_open(moment, expected):
    assert is_open(moment) is expected


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (_at(25, 7), _at(25, 9)),  # same day
        (_at(25, 19), _at(26, 9)),  # next day
        (_at(28, 14), _at(30, 9)),  # Saturday afternoon -> Monday
        (_at(29, 10), _at(30, 9)),  # Sunday -> Monday
        (_at(25, 10), _at(25, 10)),  # open now
    ],
)
def test_next_opening(moment, expected):
    assert next_opening(moment) == expected
