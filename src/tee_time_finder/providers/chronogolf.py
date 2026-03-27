from __future__ import annotations

from typing import Any

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest, TeeTime
from tee_time_finder.providers.base import BookingProvider
from tee_time_finder.providers.json_api import JsonApiProvider
from tee_time_finder.utils import (
    append_query_params,
    normalize_course_datetime,
    parse_datetime,
    render_template,
)


class ChronoGolfProvider(BookingProvider):
    DEFAULT_BASE_URL = "https://www.chronogolf.com/marketplace"
    DEFAULT_HEADERS = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    def __init__(self) -> None:
        self.fallback_provider = JsonApiProvider()

    def search(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        http_client: HttpClient,
    ) -> list[TeeTime]:
        config = course.provider_config
        if _uses_generic_json_api_config(config):
            return self.fallback_provider.search(course, request, http_client)

        club_id = str(_require(config, "club_id"))
        external_course_id = str(_require(config, "course_id"))
        affiliation_type_id = str(_require(config, "affiliation_type_id"))
        base_url = str(config.get("marketplace_base_url", self.DEFAULT_BASE_URL)).rstrip("/")

        headers = dict(self.DEFAULT_HEADERS)
        headers.update(
            {
                key: str(value)
                for key, value in (config.get("headers") or {}).items()
            }
        )

        results_by_time: dict[tuple[str, Any], TeeTime] = {}
        for hole_count in _hole_counts(config, request):
            url = append_query_params(
                f"{base_url}/clubs/{club_id}/teetimes",
                {
                    "date": request.date.isoformat(),
                    "course_id": external_course_id,
                    "affiliation_type_ids": ",".join([affiliation_type_id] * request.players),
                    "nb_holes": hole_count,
                },
            )
            payload = http_client.request_json(url, headers=headers)
            items = payload
            if isinstance(payload, dict):
                items = payload.get("teetimes")
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                tee_time = self._build_tee_time(course, request, item, hole_count)
                if tee_time is None or not tee_time.matches(request):
                    continue
                key = (tee_time.starts_at.isoformat(), tee_time.booking_url)
                results_by_time[key] = _merge_tee_times(results_by_time.get(key), tee_time)

        return list(results_by_time.values())

    def _build_tee_time(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        item: dict[str, Any],
        hole_count: int,
    ) -> TeeTime | None:
        if item.get("out_of_capacity") or item.get("frozen"):
            return None

        time_value = _to_str(item.get("start_time"))
        if not time_value:
            return None
        date_value = _to_str(item.get("date")) or request.date.isoformat()
        starts_at = normalize_course_datetime(
            parse_datetime(date_value, time_value),
            course.timezone,
        )
        price = _average_green_fee(item)
        rate_name = _rate_name(item, course.provider_config)
        booking_url = _render_booking_url(course, course.provider_config, starts_at, item)
        available_players = _to_int(item.get("free_slots")) or request.players
        return TeeTime(
            course_id=course.id,
            course_name=course.name,
            provider=course.provider,
            starts_at=starts_at,
            available_players=available_players,
            player_options=(request.players,),
            price=price,
            price_min=price,
            price_max=price,
            holes=hole_count,
            hole_options=(hole_count,),
            rate_name=rate_name,
            booking_url=booking_url or course.booking_url,
            raw={
                "item": item,
                "requested_holes": hole_count,
            },
        )


def _average_green_fee(item: dict[str, Any]) -> float | None:
    green_fees = item.get("green_fees")
    if not isinstance(green_fees, list):
        return None
    prices = [
        price
        for fee in green_fees
        if isinstance(fee, dict) and (price := _to_float(fee.get("subtotal"))) is not None
    ]
    if not prices:
        return None
    return sum(prices) / len(prices)


def _hole_counts(config: dict[str, Any], request: SearchRequest) -> tuple[int, ...]:
    if request.holes is not None:
        return (request.holes,)
    values = _to_int_tuple(config.get("supported_holes"))
    return values or (9, 18)


def _to_int_tuple(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        return ()
    parsed = sorted({_to_int(item) for item in value if _to_int(item) is not None})
    return tuple(parsed)


def _merge_tee_times(existing: TeeTime | None, new: TeeTime) -> TeeTime:
    if existing is None:
        return new

    hole_options = _merge_options(existing.hole_options, new.hole_options)
    player_options = _merge_options(existing.player_options, new.player_options)
    price_min, price_max = _merge_price_range(existing, new)
    price = price_min
    rate_name = existing.rate_name if existing.rate_name == new.rate_name else existing.rate_name or new.rate_name
    if existing.rate_name and new.rate_name and existing.rate_name != new.rate_name:
        rate_name = None

    available_players = max(
        value
        for value in (existing.available_players, new.available_players)
        if value is not None
    )

    return TeeTime(
        course_id=existing.course_id,
        course_name=existing.course_name,
        provider=existing.provider,
        starts_at=existing.starts_at,
        retrieved_at=max(existing.retrieved_at, new.retrieved_at),
        available_players=available_players,
        player_options=player_options,
        price=price,
        price_min=price_min,
        price_max=price_max,
        holes=hole_options[0] if len(hole_options) == 1 else None,
        hole_options=hole_options,
        rate_name=rate_name,
        booking_url=existing.booking_url or new.booking_url,
        raw={
            "merged": [existing.raw, new.raw],
        },
    )


def _merge_options(
    first: tuple[int, ...] | None,
    second: tuple[int, ...] | None,
) -> tuple[int, ...] | None:
    merged = sorted(set(first or ()).union(second or ()))
    if not merged:
        return None
    return tuple(merged)


def _merge_price_range(first: TeeTime, second: TeeTime) -> tuple[float | None, float | None]:
    prices = [
        value
        for value in (
            first.price_min,
            first.price_max,
            first.price,
            second.price_min,
            second.price_max,
            second.price,
        )
        if value is not None
    ]
    if not prices:
        return None, None
    return min(prices), max(prices)


def _rate_name(item: dict[str, Any], config: dict[str, Any]) -> str | None:
    configured_name = _to_str(config.get("rate_name"))
    if configured_name:
        return configured_name

    green_fees = item.get("green_fees")
    if not isinstance(green_fees, list):
        return None
    for fee in green_fees:
        if not isinstance(fee, dict):
            continue
        for field in ("affiliation_type_name", "affiliation_name", "name"):
            value = _to_str(fee.get(field))
            if value:
                return value
        affiliation_type = fee.get("affiliation_type")
        if not isinstance(affiliation_type, dict):
            continue
        for field in ("name", "title", "label"):
            value = _to_str(affiliation_type.get(field))
            if value:
                return value
    return None


def _render_booking_url(
    course: CourseDefinition,
    config: dict[str, Any],
    starts_at: Any,
    item: dict[str, Any],
) -> str | None:
    template = config.get("booking_url_template") or course.booking_url
    if not template:
        return None
    return render_template(
        str(template),
        {
            "date": starts_at.date().isoformat(),
            "time": starts_at.strftime("%H:%M"),
            "course_id": course.id,
            "club_slug": config.get("club_slug", ""),
            "teetime_id": item.get("id", ""),
            "teetime_uuid": item.get("uuid", ""),
            "external_course_id": config.get("course_id", ""),
        },
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


def _require(config: dict[str, Any], key: str) -> Any:
    value = config.get(key)
    if value in (None, ""):
        raise ValueError(f"ChronoGolf provider config requires '{key}'")
    return value


def _uses_generic_json_api_config(config: dict[str, Any]) -> bool:
    return "endpoint" in config
