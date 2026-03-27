from __future__ import annotations

import re

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest, TeeTime
from tee_time_finder.providers.base import BookingProvider
from tee_time_finder.utils import parse_datetime, render_template


class HtmlRegexProvider(BookingProvider):
    def search(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        http_client: HttpClient,
    ) -> list[TeeTime]:
        config = course.provider_config
        context = {
            "date": request.date,
            "players": request.players,
            "course_id": course.id,
            "course_name": course.name,
        }
        url = render_template(config["endpoint"], context)
        html = http_client.get_text(url, headers=config.get("headers"))
        pattern = re.compile(config["slot_pattern"], re.IGNORECASE | re.MULTILINE)
        date_value = config.get("date", request.date.isoformat())

        results: list[TeeTime] = []
        for match in pattern.finditer(html):
            groups = match.groupdict()
            tee_time = TeeTime(
                course_id=course.id,
                course_name=course.name,
                provider=course.provider,
                starts_at=parse_datetime(str(date_value), groups["time"]),
                available_players=_to_int(groups.get("players")),
                price=_to_float(groups.get("price")),
                booking_url=groups.get("url") or course.booking_url,
                raw=groups,
            )
            if tee_time.matches(request):
                results.append(tee_time)
        return results


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
