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
                candidate_rates = _candidate_rates(slot, request)
                tee_time = self._build_tee_time(course, request, facility_id, slot, candidate_rates)
                if tee_time and tee_time.matches(request):
                    results.append(tee_time)
        return results

    def _build_tee_time(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        facility_id: str,
        slot: dict[str, Any],
        candidate_rates: list[dict[str, Any]],
    ) -> TeeTime | None:
        starts_at_value = slot.get("teetime")
        if not starts_at_value or not candidate_rates:
            return None

        starts_at = normalize_course_datetime(parse_any_datetime(starts_at_value), course.timezone)
        selected_rate = _select_rate(candidate_rates, request, course.provider_config)
        player_options = _player_options(candidate_rates, slot)
        hole_options = _hole_options(candidate_rates)
        price_min, price_max = _price_range(candidate_rates)
        holes = _display_holes(request, hole_options, selected_rate)
        rate_name = _display_rate_name(candidate_rates, hole_options, selected_rate)
        available_players = max(player_options) if player_options else _to_int(slot.get("maxPlayers"))

        return TeeTime(
            course_id=course.id,
            course_name=course.name,
            provider=course.provider,
            starts_at=starts_at,
            available_players=available_players,
            player_options=player_options,
            price=price_min,
            price_min=price_min,
            price_max=price_max,
            holes=holes,
            hole_options=hole_options,
            rate_name=rate_name,
            booking_url=_render_booking_url(course, course.provider_config, facility_id, starts_at),
            raw={
                "slot": slot,
                "candidate_rates": candidate_rates,
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


def _candidate_rates(slot: dict[str, Any], request: SearchRequest) -> list[dict[str, Any]]:
    rates = [rate for rate in slot.get("rates", []) if isinstance(rate, dict)]
    if request.holes is not None:
        rates = [rate for rate in rates if _to_int(rate.get("holes")) == request.holes]
    if not rates:
        return []
    return [rate for rate in rates if _supports_players(rate, request.players)]


def _select_rate(
    rates: list[dict[str, Any]],
    request: SearchRequest,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    if not rates:
        return None

    preferred_holes = request.holes or _to_int(config.get("prefer_holes"))
    max_holes = max((_to_int(rate.get("holes")) or 0) for rate in rates)

    def sort_key(rate: dict[str, Any]) -> tuple[int, int, int, str]:
        holes = _to_int(rate.get("holes")) or 0
        preferred_rank = 0 if preferred_holes is not None and holes == preferred_holes else 1
        fallback_rank = 0 if holes == max_holes else 1
        price_rank = _extract_rate_cents(rate)
        name_rank = _to_str(rate.get("name")) or ""
        return (preferred_rank, fallback_rank, price_rank, name_rank)

    return sorted(rates, key=sort_key)[0]


def _supports_players(rate: dict[str, Any], requested_players: int) -> bool:
    allowed_players = rate.get("allowedPlayers")
    if not isinstance(allowed_players, list):
        return True
    return requested_players in allowed_players


def _player_options(rates: list[dict[str, Any]], slot: dict[str, Any]) -> tuple[int, ...] | None:
    values: set[int] = set()
    for rate in rates:
        allowed_players = rate.get("allowedPlayers")
        if not isinstance(allowed_players, list):
            continue
        for value in allowed_players:
            parsed = _to_int(value)
            if parsed is not None:
                values.add(parsed)
    if values:
        return tuple(sorted(values))
    min_players = _to_int(slot.get("minPlayers"))
    max_players = _to_int(slot.get("maxPlayers"))
    if min_players is not None and max_players is not None and min_players <= max_players:
        return tuple(range(min_players, max_players + 1))
    if max_players is not None:
        return tuple(range(1, max_players + 1))
    return None


def _hole_options(rates: list[dict[str, Any]]) -> tuple[int, ...] | None:
    values = {holes for rate in rates if (holes := _to_int(rate.get("holes"))) is not None}
    if not values:
        return None
    return tuple(sorted(values))


def _price_range(rates: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    cents_values = [_extract_rate_cents(rate) for rate in rates]
    cents_values = [value for value in cents_values if value > 0]
    if not cents_values:
        return None, None
    return _cents_to_dollars(min(cents_values)), _cents_to_dollars(max(cents_values))


def _display_holes(
    request: SearchRequest,
    hole_options: tuple[int, ...] | None,
    selected_rate: dict[str, Any] | None,
) -> int | None:
    if request.holes is not None:
        return request.holes
    if hole_options and len(hole_options) == 1:
        return hole_options[0]
    if selected_rate and hole_options and len(hole_options) == 1:
        return _to_int(selected_rate.get("holes"))
    return None


def _display_rate_name(
    rates: list[dict[str, Any]],
    hole_options: tuple[int, ...] | None,
    selected_rate: dict[str, Any] | None,
) -> str | None:
    names = {_to_str(rate.get("name")) for rate in rates if _to_str(rate.get("name"))}
    if len(names) == 1:
        return next(iter(names))
    if hole_options and len(hole_options) == 1 and selected_rate:
        return _to_str(selected_rate.get("name"))
    return None


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
