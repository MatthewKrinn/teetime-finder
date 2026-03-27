from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Any


@dataclass(slots=True)
class SearchRequest:
    date: date
    players: int
    earliest: time | None = None
    latest: time | None = None
    course_ids: set[str] | None = None


@dataclass(slots=True)
class CourseDefinition:
    id: str
    name: str
    provider: str
    timezone: str = "America/New_York"
    booking_url: str | None = None
    provider_config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TeeTime:
    course_id: str
    course_name: str
    provider: str
    starts_at: datetime
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    available_players: int | None = None
    price: float | None = None
    holes: int | None = None
    rate_name: str | None = None
    booking_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def matches(self, request: SearchRequest) -> bool:
        if self.starts_at.date() != request.date:
            return False
        if request.earliest and self.starts_at.time() < request.earliest:
            return False
        if request.latest and self.starts_at.time() > request.latest:
            return False
        if self.available_players is not None and self.available_players < request.players:
            return False
        if request.course_ids and self.course_id not in request.course_ids:
            return False
        return True
