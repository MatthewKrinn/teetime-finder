from __future__ import annotations

import json
import shlex
from dataclasses import dataclass

from tee_time_finder.response_inference import ResponseMappingSuggestion, infer_response_mapping


@dataclass(slots=True)
class ParsedCurlRequest:
    method: str
    url: str
    headers: dict[str, str]
    body_json: object | None = None
    body_text: str | None = None


def parse_curl_command(command: str) -> ParsedCurlRequest:
    tokens = shlex.split(command.strip())
    if not tokens or tokens[0] != "curl":
        raise ValueError("Expected a curl command")

    method: str | None = None
    url: str | None = None
    raw_headers: list[str] = []
    data_parts: list[str] = []

    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in {"-X", "--request"} and index + 1 < len(tokens):
            method = tokens[index + 1].upper()
            index += 2
            continue
        if token in {"-H", "--header"} and index + 1 < len(tokens):
            raw_headers.append(tokens[index + 1])
            index += 2
            continue
        if token in {"-A", "--user-agent"} and index + 1 < len(tokens):
            raw_headers.append(f"User-Agent: {tokens[index + 1]}")
            index += 2
            continue
        if token in {"-b", "--cookie"} and index + 1 < len(tokens):
            raw_headers.append(f"Cookie: {tokens[index + 1]}")
            index += 2
            continue
        if token in {"-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"} and index + 1 < len(tokens):
            data_parts.append(tokens[index + 1])
            index += 2
            continue
        if token == "--url" and index + 1 < len(tokens):
            url = tokens[index + 1]
            index += 2
            continue
        if token.startswith("http://") or token.startswith("https://"):
            url = token
        index += 1

    if url is None:
        raise ValueError("No URL was found in the curl command")

    headers = _normalize_headers(raw_headers)
    if method is None:
        method = "POST" if data_parts else "GET"

    raw_body = "&".join(data_parts) if data_parts else None
    body_json = None
    body_text = None
    if raw_body:
        try:
            body_json = json.loads(raw_body)
        except json.JSONDecodeError:
            body_text = raw_body

    return ParsedCurlRequest(
        method=method,
        url=url,
        headers=headers,
        body_json=body_json,
        body_text=body_text,
    )


def import_curl_to_course_config(
    *,
    curl_command: str,
    course_id: str,
    course_name: str,
    provider: str,
    timezone: str,
    booking_url: str | None = None,
    replacements: dict[str, str] | None = None,
    response_payload: object | None = None,
) -> dict[str, object]:
    parsed = parse_curl_command(curl_command)
    replacements = replacements or {}

    provider_config: dict[str, object] = {
        "method": parsed.method,
        "endpoint": _replace_literals(parsed.url, replacements),
        "headers": {
            key: _replace_literals(value, replacements)
            for key, value in parsed.headers.items()
        },
        "items_path": "REPLACE_ME",
        "starts_at_field": "REPLACE_ME",
        "available_players_field": "REPLACE_ME",
        "price_field": "REPLACE_ME",
        "booking_url_field": "REPLACE_ME",
    }
    if parsed.body_json is not None:
        provider_config["body_json"] = _replace_structure(parsed.body_json, replacements)
    if parsed.body_text is not None:
        provider_config["body_text"] = _replace_literals(parsed.body_text, replacements)
    if response_payload is not None:
        _apply_mapping_suggestion(provider_config, infer_response_mapping(response_payload))

    course = {
        "id": course_id,
        "name": course_name,
        "provider": provider,
        "timezone": timezone,
        "booking_url": booking_url or parsed.url,
        "provider_config": provider_config,
    }
    return {"courses": [course]}


def _normalize_headers(raw_headers: list[str]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    ignored_prefixes = ("sec-",)
    ignored_names = {"host", "content-length", "accept-encoding", "connection", "priority"}
    for header in raw_headers:
        if ":" not in header:
            continue
        name, value = header.split(":", 1)
        normalized_name = name.strip()
        lowered = normalized_name.lower()
        if lowered in ignored_names or lowered.startswith(ignored_prefixes):
            continue
        filtered[normalized_name] = value.strip()
    return filtered


def _replace_structure(value: object, replacements: dict[str, str]) -> object:
    if isinstance(value, str):
        return _replace_literals(value, replacements)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        rendered = _replace_literals(str(value), replacements)
        return rendered if rendered != str(value) else value
    if isinstance(value, list):
        return [_replace_structure(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _replace_structure(item, replacements) for key, item in value.items()}
    return value


def _replace_literals(value: str, replacements: dict[str, str]) -> str:
    rendered = value
    for old, new in replacements.items():
        rendered = rendered.replace(old, new)
    return rendered


def _apply_mapping_suggestion(
    provider_config: dict[str, object],
    suggestion: ResponseMappingSuggestion,
) -> None:
    if suggestion.items_path is not None:
        provider_config["items_path"] = suggestion.items_path
    if suggestion.starts_at_field:
        provider_config["starts_at_field"] = suggestion.starts_at_field
        provider_config.pop("time_field", None)
        provider_config.pop("date_field", None)
    else:
        provider_config.pop("starts_at_field", None)
        if suggestion.time_field:
            provider_config["time_field"] = suggestion.time_field
        if suggestion.date_field:
            provider_config["date_field"] = suggestion.date_field
    if suggestion.price_field:
        provider_config["price_field"] = suggestion.price_field
    if suggestion.available_players_field:
        provider_config["available_players_field"] = suggestion.available_players_field
    if suggestion.booking_url_field:
        provider_config["booking_url_field"] = suggestion.booking_url_field
