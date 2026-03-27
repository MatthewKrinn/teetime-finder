from __future__ import annotations

import json
from typing import Any

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest, TeeTime
from tee_time_finder.providers.base import BookingProvider
from tee_time_finder.utils import (
    append_query_params,
    build_template_context,
    get_path,
    normalize_course_datetime,
    parse_any_datetime,
    parse_datetime,
    render_structure,
    render_template,
)


class JsonApiProvider(BookingProvider):
    def search(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        http_client: HttpClient,
    ) -> list[TeeTime]:
        config = course.provider_config
        context = build_template_context(
            course_id=course.id,
            course_name=course.name,
            booking_url=course.booking_url,
            provider_variables=config.get("variables"),
            request_date=request.date,
            players=request.players,
            earliest=request.earliest,
            latest=request.latest,
        )
        url = render_template(config["endpoint"], context)
        url = append_query_params(url, render_structure(config.get("query_params"), context))
        headers = {
            key: str(value)
            for key, value in render_structure(config.get("headers", {}), context).items()
        }
        body = _build_body(config, context)
        payload = http_client.request_json(
            url,
            method=config.get("method", "GET"),
            headers=headers,
            body=body,
        )
        items = get_path(payload, config.get("items_path"), payload)
        if not isinstance(items, list):
            return []

        results: list[TeeTime] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tee_time = self._build_tee_time(course, request, item, config, context)
            if tee_time and tee_time.matches(request):
                results.append(tee_time)
        return results

    def _build_tee_time(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        item: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> TeeTime | None:
        starts_at = _build_starts_at(item, config, request)
        if starts_at is None:
            return None
        starts_at = normalize_course_datetime(starts_at, course.timezone)

        time_value = get_path(item, config.get("time_field", "time"))
        booking_url = get_path(item, config.get("booking_url_field"))
        if not booking_url and config.get("booking_url_template"):
            item_context = dict(context)
            item_context.update({key: value for key, value in item.items() if isinstance(key, str)})
            booking_url = render_template(config["booking_url_template"], item_context)
        return TeeTime(
            course_id=course.id,
            course_name=course.name,
            provider=course.provider,
            starts_at=starts_at,
            available_players=_to_int(get_path(item, config.get("available_players_field"))),
            price=_to_float(get_path(item, config.get("price_field"))),
            holes=_to_int(get_path(item, config.get("holes_field"))),
            rate_name=_to_str(get_path(item, config.get("rate_name_field"))),
            booking_url=booking_url or course.booking_url,
            raw=item,
        )


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _build_body(config: dict[str, Any], context: dict[str, Any]) -> str | None:
    if "body_json" in config:
        return json.dumps(render_structure(config["body_json"], context))
    if "body_text" in config:
        rendered = render_structure(config["body_text"], context)
        return str(rendered)
    return None


def _build_starts_at(
    item: dict[str, Any],
    config: dict[str, Any],
    request: SearchRequest,
) -> Any:
    starts_at_field = config.get("starts_at_field")
    if starts_at_field:
        value = get_path(item, starts_at_field)
        if value in (None, ""):
            return None
        return parse_any_datetime(value, fallback_date=request.date)

    time_value = get_path(item, config.get("time_field", "time"))
    if not time_value:
        return None
    date_value = get_path(item, config.get("date_field")) or request.date.isoformat()
    return parse_datetime(str(date_value), str(time_value))
