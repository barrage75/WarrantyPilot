from collections.abc import Callable
from datetime import UTC, date, datetime, time

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def checked_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Une date avec fuseau horaire est requise")
    return value.astimezone(UTC)


class FollowUpClock:
    def __init__(self, clock: Clock = utc_now, demo_today: date | None = None) -> None:
        self.clock, self.demo_today = clock, demo_today

    def now(self) -> datetime:
        if self.demo_today is not None:
            return datetime.combine(self.demo_today, time.min, UTC)
        return checked_utc(self.clock())
