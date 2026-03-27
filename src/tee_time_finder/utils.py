from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

TOKEN_ONLY_PATTERN = re.compile(r"^\{([a-zA-Z_][a-zA-Z0-9_]*)\}$")


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_time(value: str) -> time:
    value = value.strip()
    formats = ("%H:%M", "%H:%M:%S", "%I:%M %p")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format: {value}")


def parse_holes(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"", "either", "any"}:
        return None
    if normalized == "9":
        return 9
    if normalized == "18":
        return 18
    raise ValueError("holes must be 9, 18, or either")


def parse_datetime(date_value: str, time_value: str) -> datetime:
    return datetime.combine(parse_date(date_value), parse_time(time_value))


def parse_any_datetime(value: object, fallback_date: date | None = None) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return _parse_epoch(float(value))

    normalized = str(value).strip()
    if not normalized:
        raise ValueError("Expected a non-empty datetime value")

    if normalized.isdigit():
        return _parse_epoch(float(normalized))

    if fallback_date:
        try:
            return datetime.combine(fallback_date, parse_time(normalized))
        except ValueError:
            pass

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    formats = (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %I:%M %p",
    )
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported datetime format: {value}")


def normalize_course_datetime(value: datetime, timezone_name: str) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(ZoneInfo(timezone_name)).replace(tzinfo=None)


def append_query_params(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    split = urlsplit(url)
    existing = parse_qsl(split.query, keep_blank_values=True)
    rendered = [(key, _to_query_value(value)) for key, value in params.items()]
    query = urlencode(existing + rendered)
    return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))


def get_path(data: Any, path: str | None, default: Any = None) -> Any:
    if path is None:
        return default
    if path in {"", "."}:
        return data
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
            continue
        if isinstance(current, list):
            if not part.isdigit():
                return default
            index = int(part)
            if index < 0 or index >= len(current):
                return default
            current = current[index]
            continue
        return default
    return current


def render_template(template: str, context: dict[str, Any]) -> str:
    normalized = {
        key: value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in context.items()
    }
    return template.format(**normalized)


def render_structure(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        token_match = TOKEN_ONLY_PATTERN.match(value)
        if token_match and token_match.group(1) in context:
            return context[token_match.group(1)]
        return render_template(value, context)
    if isinstance(value, dict):
        return {key: render_structure(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [render_structure(item, context) for item in value]
    return value


def build_template_context(
    *,
    course_id: str,
    course_name: str,
    booking_url: str | None,
    provider_variables: dict[str, Any] | None,
    request_date: date,
    players: int,
    earliest: time | None = None,
    latest: time | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "date": request_date.isoformat(),
        "players": players,
        "course_id": course_id,
        "course_name": course_name,
        "booking_url": booking_url or "",
    }
    if earliest is not None:
        context["earliest"] = earliest.isoformat(timespec="minutes")
    if latest is not None:
        context["latest"] = latest.isoformat(timespec="minutes")
    context.update(provider_variables or {})
    return context


def _parse_epoch(value: float) -> datetime:
    if value > 1_000_000_000_000:
        value /= 1000
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _to_query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
