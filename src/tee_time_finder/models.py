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
    holes: int | None = None
    course_ids: set[str] | None = None


@dataclass(slots=True)
class CourseDefinition:
    id: str
    name: str
    provider: str
    timezone: str = "America/New_York"
    group: str | None = None
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
    player_options: tuple[int, ...] | None = None
    price: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    holes: int | None = None
    hole_options: tuple[int, ...] | None = None
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
        if request.holes is not None:
            if self.holes is not None and self.holes != request.holes:
                return False
            if self.holes is None:
                if not self.hole_options or request.holes not in self.hole_options:
                    return False
        available_players = self.available_players
        if available_players is None and self.player_options:
            available_players = max(self.player_options)
        if available_players is not None and available_players < request.players:
            return False
        if request.course_ids and self.course_id not in request.course_ids:
            return False
        return True
