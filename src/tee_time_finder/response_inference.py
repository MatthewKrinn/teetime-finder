from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tee_time_finder.utils import parse_time


@dataclass(slots=True)
class ResponseMappingSuggestion:
    items_path: str | None = None
    starts_at_field: str | None = None
    date_field: str | None = None
    time_field: str | None = None
    price_field: str | None = None
    available_players_field: str | None = None
    booking_url_field: str | None = None


@dataclass(slots=True)
class _FieldChoice:
    path: str | None = None
    score: int = 0


def infer_response_mapping(payload: object) -> ResponseMappingSuggestion:
    best_suggestion = ResponseMappingSuggestion()
    best_score = -1
    for path, items in _iter_list_candidates(payload):
        suggestion, score = _infer_from_items(path, items)
        if score > best_score:
            best_score = score
            best_suggestion = suggestion
    return best_suggestion


def _iter_list_candidates(value: object, path: str = ""):
    if isinstance(value, list):
        items = [item for item in value if isinstance(item, dict)]
        if items:
            yield path, items[:5]
        for index, item in enumerate(value[:3]):
            child_path = f"{path}.{index}" if path else str(index)
            yield from _iter_list_candidates(item, child_path)
        return

    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from _iter_list_candidates(item, child_path)


def _infer_from_items(
    path: str,
    items: list[dict[str, Any]],
) -> tuple[ResponseMappingSuggestion, int]:
    field_samples = _collect_field_samples(items)
    starts_at = _pick_best_field(field_samples, _score_starts_at, threshold=11)
    time_field = _FieldChoice()
    date_field = _FieldChoice()
    if not starts_at.path:
        time_field = _pick_best_field(field_samples, _score_time, threshold=11)
        date_field = _pick_best_field(field_samples, _score_date, threshold=10)
    price_field = _pick_best_field(field_samples, _score_price, threshold=10)
    players_field = _pick_best_field(field_samples, _score_players, threshold=10)
    booking_url_field = _pick_best_field(field_samples, _score_booking_url, threshold=10)

    suggestion = ResponseMappingSuggestion(
        items_path=path,
        starts_at_field=starts_at.path,
        date_field=date_field.path,
        time_field=time_field.path,
        price_field=price_field.path,
        available_players_field=players_field.path,
        booking_url_field=booking_url_field.path,
    )

    score = _score_items_path(path)
    if starts_at.path:
        score += starts_at.score * 5
    else:
        score += time_field.score * 4
        score += date_field.score * 2
    score += price_field.score * 3
    score += players_field.score * 3
    score += booking_url_field.score * 2
    score += min(len(items), 5)
    return suggestion, score


def _collect_field_samples(items: list[dict[str, Any]]) -> dict[str, list[object]]:
    samples: dict[str, list[object]] = {}
    for item in items[:5]:
        for path, value in _iter_leaf_values(item):
            samples.setdefault(path, []).append(value)
    return samples


def _iter_leaf_values(value: object, path: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from _iter_leaf_values(item, child_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value[:3]):
            child_path = f"{path}.{index}" if path else str(index)
            yield from _iter_leaf_values(item, child_path)
        return
    if path:
        yield path, value


def _pick_best_field(
    field_samples: dict[str, list[object]],
    scorer,
    *,
    threshold: int,
) -> _FieldChoice:
    best = _FieldChoice()
    for path, values in field_samples.items():
        score = sum(scorer(path, value) for value in values)
        if score > best.score:
            best = _FieldChoice(path=path, score=score)
    if best.score < threshold:
        return _FieldChoice()
    return best


def _score_items_path(path: str) -> int:
    normalized = _normalize_name(path)
    score = 0
    positive_terms = ("tee", "time", "slot", "result", "availability", "offer")
    negative_terms = ("image", "photo", "review", "logo")
    score += sum(4 for term in positive_terms if term in normalized)
    score -= sum(5 for term in negative_terms if term in normalized)
    return score


def _score_starts_at(path: str, value: object) -> int:
    if not _looks_like_full_datetime(value):
        return 0
    normalized = _normalize_name(path)
    score = 8
    strong_terms = (
        "startsat",
        "startdatetime",
        "starttime",
        "datetime",
        "teetime",
        "teedatetime",
        "slottime",
    )
    if any(term in normalized for term in strong_terms):
        score += 7
    elif "time" in normalized and "date" in normalized:
        score += 5
    elif any(term in normalized for term in ("time", "start", "tee")):
        score += 2
    return score


def _score_time(path: str, value: object) -> int:
    if not _looks_like_time_only(value):
        return 0
    normalized = _normalize_name(path)
    score = 7
    strong_terms = ("time", "teetime", "starttime", "start", "tee")
    if any(term in normalized for term in strong_terms):
        score += 6
    return score


def _score_date(path: str, value: object) -> int:
    if not _looks_like_date_only(value):
        return 0
    normalized = _normalize_name(path)
    score = 6
    if "date" in normalized:
        score += 6
    return score


def _score_price(path: str, value: object) -> int:
    numeric = _to_float(value)
    if numeric is None:
        return 0
    normalized = _normalize_name(path)
    score = 6
    if 0 < numeric < 1000:
        score += 2
    price_terms = ("price", "fee", "rate", "cost", "amount", "greenfee", "greensfee")
    if any(term in normalized for term in price_terms):
        score += 6
    if normalized.endswith("id") or "identifier" in normalized:
        score -= 5
    return score


def _score_players(path: str, value: object) -> int:
    count = _to_int(value)
    if count is None:
        return 0
    normalized = _normalize_name(path)
    score = 0
    if 1 <= count <= 8:
        score += 8
    elif 0 <= count <= 20:
        score += 3
    strong_terms = (
        "availableplayers",
        "playersavailable",
        "maxplayers",
        "openspots",
        "spotsavailable",
        "remaining",
        "availability",
    )
    weak_terms = ("players", "slots")
    if any(term in normalized for term in strong_terms):
        score += 6
    elif any(term in normalized for term in weak_terms):
        score += 2
    if normalized.endswith("id") or "identifier" in normalized:
        score -= 5
    return score


def _score_booking_url(path: str, value: object) -> int:
    if not _looks_like_url(value):
        return 0
    normalized = _normalize_name(path)
    score = 6
    booking_terms = ("bookingurl", "book", "reserve", "reservation", "url", "href", "link")
    if any(term in normalized for term in booking_terms):
        score += 6
    bad_terms = ("image", "photo", "logo", "review", "api", "auth")
    if any(term in normalized for term in bad_terms):
        score -= 8
    return score


def _looks_like_full_datetime(value: object) -> bool:
    if isinstance(value, (int, float)):
        return abs(float(value)) >= 1_000_000_000

    text = str(value).strip()
    if not text or ":" not in text:
        return False
    if text.isdigit():
        return len(text) >= 10

    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        pass

    formats = (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %I:%M %p",
    )
    for fmt in formats:
        try:
            datetime.strptime(text, fmt)
            return True
        except ValueError:
            continue
    return False


def _looks_like_time_only(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or "-" in text or "/" in text or "T" in text:
        return False
    try:
        parse_time(text)
    except ValueError:
        return False
    return True


def _looks_like_date_only(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or ":" in text:
        return False
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", text) or re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", text))


def _looks_like_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    return text.startswith(("http://", "https://", "/"))


def _to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("$", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _normalize_name(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", path.lower())
