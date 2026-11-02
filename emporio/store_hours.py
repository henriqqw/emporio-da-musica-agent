"""Opening hours from the manual, section 2 (rule R-INFO-4). Holidays are not known."""

from datetime import datetime, time, timedelta

# weekday (Monday=0) -> (opens, closes); missing day = closed
OPENING_HOURS = {
    **{day: (time(9), time(18)) for day in range(5)},
    5: (time(9), time(13)),
}


def is_open(now: datetime) -> bool:
    hours = OPENING_HOURS.get(now.weekday())
    return hours is not None and hours[0] <= now.time() < hours[1]


def next_opening(now: datetime) -> datetime:
    """When the team is next available; `now` itself if the store is open."""
    if is_open(now):
        return now
    for days_ahead in range(8):
        day = now + timedelta(days=days_ahead)
        hours = OPENING_HOURS.get(day.weekday())
        if hours is None:
            continue
        opening = day.replace(hour=hours[0].hour, minute=0, second=0, microsecond=0)
        if opening > now:
            return opening
    raise AssertionError("the store opens at least once a week")
