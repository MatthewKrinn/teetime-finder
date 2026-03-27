from __future__ import annotations

import json
from typing import Any

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest, TeeTime
from tee_time_finder.providers.base import BookingProvider
from tee_time_finder.providers.site_family import SiteFamilyProvider
from tee_time_finder.utils import parse_datetime, render_template


class TenForeProvider(BookingProvider):
    DEFAULT_API_URL = "https://swan.tenfore.golf/api"
    DEFAULT_APP_ID = 71

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

        golf_course_id = _to_int(_require(config, "golf_course_id"))
        if golf_course_id is None:
            raise ValueError("TenFore provider_config 'golf_course_id' must be an integer")

        base_url = str(config.get("api_url", self.DEFAULT_API_URL)).rstrip("/")
        payload = http_client.request_json(
            f"{base_url}/BookingEngineV4/booking-times",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "golfCourseId": golf_course_id,
                    "subCourseId": _to_int(config.get("sub_course_id")),
                    "dateFrom": request.date.isoformat(),
                    "appId": _to_int(config.get("app_id")) or self.DEFAULT_APP_ID,
                }
            ),
        )

        slots = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(slots, list):
            return []

        results: list[TeeTime] = []
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            tee_time = self._build_tee_time(course, slot)
            if tee_time and tee_time.matches(request):
                results.append(tee_time)
        return results

    def _build_tee_time(
        self,
        course: CourseDefinition,
        slot: dict[str, Any],
    ) -> TeeTime | None:
        date_value = _to_str(slot.get("date"))
        time_value = _to_str(slot.get("time"))
        if not date_value or not time_value:
            return None

        starts_at = parse_datetime(date_value, time_value)
        selected_holes = _select_holes(slot, course.provider_config)

        return TeeTime(
            course_id=course.id,
            course_name=course.name,
            provider=course.provider,
            starts_at=starts_at,
            available_players=_to_int(slot.get("spots")),
            price=_extract_price(slot, selected_holes),
            holes=selected_holes,
            rate_name=_to_str(slot.get("feeTitle")) or _to_str(slot.get("title")),
            booking_url=_render_booking_url(course, course.provider_config, starts_at),
            raw={
                "slot": slot,
                "selected_holes": selected_holes,
            },
        )


def _select_holes(slot: dict[str, Any], config: dict[str, Any]) -> int | None:
    preferred_holes = _to_int(config.get("prefer_holes")) or _to_int(config.get("default_holes"))
    if preferred_holes is None:
        preferred_holes = _to_int(slot.get("maxHoles"))

    if preferred_holes in {9, 18} and _extract_price(slot, preferred_holes) is not None:
        return preferred_holes

    for holes in (18, 9):
        if _extract_price(slot, holes) is not None:
            return holes
    return preferred_holes


def _extract_price(slot: dict[str, Any], holes: int | None) -> float | None:
    candidates: list[str] = []
    if holes in {9, 18}:
        candidates.extend([f"fullPrice{holes}", f"feePrice{holes}"])
    candidates.extend(["fullPrice18", "feePrice18", "fullPrice9", "feePrice9"])

    seen: set[str] = set()
    for field in candidates:
        if field in seen:
            continue
        seen.add(field)
        value = _to_float(slot.get(field))
        if value is not None and value > 0:
            return value
    return None


def _render_booking_url(
    course: CourseDefinition,
    config: dict[str, Any],
    starts_at: Any,
) -> str | None:
    template = config.get("booking_url_template") or course.booking_url
    vanity_name = _to_str(config.get("vanity_name"))
    if not template and vanity_name:
        template = f"https://fox.tenfore.golf/{vanity_name}"
    if not template:
        return None
    return render_template(
        str(template),
        {
            "date": starts_at.date().isoformat(),
            "time": starts_at.strftime("%H:%M"),
            "course_id": course.id,
            "golf_course_id": _require(config, "golf_course_id"),
            "sub_course_id": config.get("sub_course_id") or "",
            "vanity_name": vanity_name or "",
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
        raise ValueError(f"TenFore provider_config requires '{key}'")
    return value


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
