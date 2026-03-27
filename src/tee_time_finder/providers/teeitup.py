from __future__ import annotations

from datetime import datetime
from typing import Any

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest, TeeTime
from tee_time_finder.providers.base import BookingProvider
from tee_time_finder.providers.site_family import SiteFamilyProvider
from tee_time_finder.utils import append_query_params, normalize_course_datetime, parse_any_datetime, render_template


class TeeItUpProvider(BookingProvider):
    DEFAULT_BE_API_URL = "https://phx-api-be-east-1b.kenna.io"
    ALIAS_HEADER = "x-be-alias"

    def __init__(self) -> None:
        self.fallback_provider = SiteFamilyProvider()

    def search(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        http_client: HttpClient,
    ) -> list[TeeTime]:
        config = course.provider_config
        if _uses_generic_site_family_config(config):
            return self.fallback_provider.search(course, request, http_client)

        facility_id = str(_require(config, "facility_id"))
        alias = str(_require(config, "alias"))
        base_url = str(config.get("be_api_url", self.DEFAULT_BE_API_URL)).rstrip("/")
        url = append_query_params(
            f"{base_url}/v2/tee-times",
            _build_query_params(config, request, facility_id),
        )
        payload = http_client.request_json(url, headers={self.ALIAS_HEADER: alias})
        if not isinstance(payload, list):
            return []

        results: list[TeeTime] = []
        for group in payload:
            if not isinstance(group, dict):
                continue
            tee_times = group.get("teetimes")
            if not isinstance(tee_times, list):
                continue
            for slot in tee_times:
                if not isinstance(slot, dict):
                    continue
                tee_time = self._build_tee_time(course, request, facility_id, slot)
                if tee_time and tee_time.matches(request):
                    results.append(tee_time)
        return results

    def _build_tee_time(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        facility_id: str,
        slot: dict[str, Any],
    ) -> TeeTime | None:
        starts_at_value = slot.get("teetime")
        if not starts_at_value:
            return None

        starts_at = normalize_course_datetime(parse_any_datetime(starts_at_value), course.timezone)
        selected_rate = _select_rate(slot, request, course.provider_config)
        available_players = _available_players(slot, selected_rate)

        return TeeTime(
            course_id=course.id,
            course_name=course.name,
            provider=course.provider,
            starts_at=starts_at,
            available_players=available_players,
            price=_cents_to_dollars(_extract_rate_cents(selected_rate)),
            holes=_to_int(selected_rate.get("holes")) if selected_rate else None,
            rate_name=_to_str(selected_rate.get("name")) if selected_rate else None,
            booking_url=_render_booking_url(course, course.provider_config, facility_id, starts_at),
            raw={
                "slot": slot,
                "selected_rate": selected_rate,
            },
        )


def _build_query_params(
    config: dict[str, Any],
    request: SearchRequest,
    facility_id: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "date": request.date.isoformat(),
        "facilityIds": facility_id,
    }
    if config.get("return_promoted_rates") is not None:
        params["returnPromotedRates"] = bool(config["return_promoted_rates"])
    if config.get("promotion_code"):
        params["promotionCode"] = config["promotion_code"]
    if config.get("customer_id"):
        params["customerId"] = config["customer_id"]
    if config.get("date_max"):
        params["dateMax"] = config["date_max"]
    return params


def _select_rate(
    slot: dict[str, Any],
    request: SearchRequest,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    rates = [rate for rate in slot.get("rates", []) if isinstance(rate, dict)]
    if not rates:
        return None

    requested_players = request.players
    supported_rates = [rate for rate in rates if _supports_players(rate, requested_players)]
    candidates = supported_rates or rates
    preferred_holes = _to_int(config.get("prefer_holes"))
    max_holes = max((_to_int(rate.get("holes")) or 0) for rate in candidates)

    def sort_key(rate: dict[str, Any]) -> tuple[int, int, int, str]:
        holes = _to_int(rate.get("holes")) or 0
        preferred_rank = 0 if preferred_holes is not None and holes == preferred_holes else 1
        fallback_rank = 0 if holes == max_holes else 1
        price_rank = _extract_rate_cents(rate)
        name_rank = _to_str(rate.get("name")) or ""
        return (preferred_rank, fallback_rank, price_rank, name_rank)

    return sorted(candidates, key=sort_key)[0]


def _supports_players(rate: dict[str, Any], requested_players: int) -> bool:
    allowed_players = rate.get("allowedPlayers")
    if not isinstance(allowed_players, list):
        return True
    return requested_players in allowed_players


def _available_players(slot: dict[str, Any], rate: dict[str, Any] | None) -> int | None:
    remaining_players = _remaining_players(slot)
    if rate:
        allowed_players = rate.get("allowedPlayers")
        if isinstance(allowed_players, list):
            allowed_values = [_to_int(value) for value in allowed_players]
            allowed_candidates = [value for value in allowed_values if value is not None]
            if allowed_candidates:
                allowed_max = max(allowed_candidates)
                if remaining_players is not None:
                    return min(remaining_players, allowed_max)
                return allowed_max
    return remaining_players


def _remaining_players(slot: dict[str, Any]) -> int | None:
    max_players = _to_int(slot.get("maxPlayers"))
    if max_players is None:
        return None
    booked_players = _to_int(slot.get("bookedPlayers"))
    if booked_players is None:
        return max_players
    return max(max_players - booked_players, 0)


def _extract_rate_cents(rate: dict[str, Any] | None) -> int:
    if not rate:
        return 0
    for field in ("greenFeeCart", "greenFeeWalking", "dueOnlineRiding", "dueOnlineWalking"):
        value = _to_int(rate.get(field))
        if value is not None:
            return value
    return 0


def _cents_to_dollars(value: int) -> float | None:
    if value <= 0:
        return None
    return value / 100


def _render_booking_url(
    course: CourseDefinition,
    config: dict[str, Any],
    facility_id: str,
    starts_at: datetime,
) -> str | None:
    template = config.get("booking_url_template") or course.booking_url
    if not template:
        return None
    return render_template(
        str(template),
        {
            "date": starts_at.date().isoformat(),
            "time": starts_at.strftime("%H:%M"),
            "facility_id": facility_id,
            "course_id": course.id,
        },
    )


def _uses_generic_site_family_config(config: dict[str, Any]) -> bool:
    generic_keys = {
        "endpoint",
        "items_path",
        "response_format",
        "starts_at_field",
        "time_field",
        "body_json",
        "body_text",
        "query_params",
    }
    return any(key in config for key in generic_keys)


def _require(config: dict[str, Any], key: str) -> Any:
    value = config.get(key)
    if value in (None, ""):
        raise ValueError(f"TeeItUp provider_config requires '{key}'")
    return value


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
