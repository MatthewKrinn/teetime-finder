from __future__ import annotations

import argparse
import json
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tee_time_finder.config import load_courses
from tee_time_finder.models import CourseDefinition, SearchRequest
from tee_time_finder.service import TeeTimeService
from tee_time_finder.utils import parse_holes, parse_time

STATIC_DIR = Path(__file__).with_name("static")

def run_server(config_path: str, host: str = "127.0.0.1", port: int = 8080) -> None:
    courses = load_courses(config_path)
    service = TeeTimeService(courses)
    handler = build_handler(service, host=host, port=port)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving Tee Time Finder API at http://{host}:{port}")
    server.serve_forever()


def build_handler(service: TeeTimeService, host: str, port: int):
    class TeeTimeHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._write_html(_read_static_text("index.html"))
                return
            if parsed.path.startswith("/assets/"):
                self._write_static_asset(parsed.path.removeprefix("/assets/"))
                return
            if parsed.path in {"/api", "/api/"}:
                self._write_json(
                    {
                        "name": "tee-time-finder",
                        "version": "0.1.0",
                        "docs_url": f"http://{host}:{port}/docs",
                        "openapi_url": f"http://{host}:{port}/openapi.json",
                        "search_url": f"http://{host}:{port}/api/search",
                        "courses_url": f"http://{host}:{port}/api/courses",
                    }
                )
                return
            if parsed.path == "/docs":
                self._write_html(render_docs(host, port))
                return
            if parsed.path == "/openapi.json":
                self._write_json(build_openapi_spec(host, port))
                return
            if parsed.path == "/api/courses":
                self._write_json(serialize_courses(service.list_courses()))
                return
            if parsed.path == "/api/search":
                try:
                    params = parse_qs(parsed.query)
                    request = parse_request(params)
                    results = service.search(request)
                except ValueError as exc:
                    self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json(serialize_results(results))
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args) -> None:
            return

        def _write_html(self, content: str) -> None:
            encoded = content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _write_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
            encoded = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _write_static_asset(self, asset_name: str) -> None:
            try:
                encoded, content_type = _read_static_asset(asset_name)
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return TeeTimeHandler


def parse_request(params: dict[str, list[str]]) -> SearchRequest:
    date_value = first(params, "date")
    players_value = first(params, "players")
    if not date_value or not players_value:
        raise ValueError("date and players are required")
    course_ids = set(params.get("course_id", [])) or None
    return SearchRequest(
        date=date.fromisoformat(date_value),
        players=int(players_value),
        earliest=parse_time(first(params, "earliest")) if first(params, "earliest") else None,
        latest=parse_time(first(params, "latest")) if first(params, "latest") else None,
        holes=parse_holes(first(params, "holes")),
        course_ids=course_ids,
    )


def first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    return values[0] if values else None


def serialize_courses(courses: list[CourseDefinition]) -> list[dict[str, object]]:
    return [
        {
            "id": course.id,
            "name": course.name,
            "provider": course.provider,
            "group": course.group or infer_course_group(course),
        }
        for course in courses
    ]


def infer_course_group(course: CourseDefinition) -> str:
    if course.group:
        return course.group
    alias = str(course.provider_config.get("alias", "")).strip().lower()
    if alias == "fairfax-county-mco":
        return "Fairfax"
    if alias == "nova-parks":
        return "Pohick"
    if course.provider == "tenfore":
        return "MCG"
    if "pohick" in course.id.lower():
        return "Pohick"
    return course.provider.replace("_", " ").title()


def serialize_results(results: list) -> list[dict[str, object]]:
    return [
        {
            "course_id": item.course_id,
            "course_name": item.course_name,
            "provider": item.provider,
            "starts_at": item.starts_at.isoformat(),
            "retrieved_at": item.retrieved_at.isoformat(),
            "available_players": item.available_players,
            "player_options": list(item.player_options) if item.player_options else None,
            "price": item.price,
            "price_min": item.price_min,
            "price_max": item.price_max,
            "holes": item.holes,
            "hole_options": list(item.hole_options) if item.hole_options else None,
            "rate_name": item.rate_name,
            "booking_url": item.booking_url,
        }
        for item in results
    ]


def build_openapi_spec(host: str, port: int) -> dict[str, object]:
    server_url = f"http://{host}:{port}"
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Tee Time Finder API",
            "version": "0.1.0",
            "description": "Search tee times across multiple golf booking providers.",
        },
        "servers": [{"url": server_url}],
        "paths": {
            "/api/courses": {
                "get": {
                    "summary": "List configured courses",
                    "responses": {
                        "200": {
                            "description": "Configured courses",
                        }
                    },
                }
            },
            "/api/search": {
                "get": {
                    "summary": "Search tee times",
                    "parameters": [
                        parameter("date", "query", True, "Search date in YYYY-MM-DD format", "string", "date"),
                        parameter("players", "query", True, "Required player count", "integer"),
                        parameter("earliest", "query", False, "Earliest time in HH:MM format", "string"),
                        parameter("latest", "query", False, "Latest time in HH:MM format", "string"),
                        parameter("holes", "query", False, "Optional holes filter: 9, 18, or either", "string"),
                        {
                            "name": "course_id",
                            "in": "query",
                            "required": False,
                            "description": "Optional course id filter. Repeat to include multiple courses.",
                            "schema": {"type": "array", "items": {"type": "string"}},
                            "style": "form",
                            "explode": True,
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Normalized tee time results",
                        },
                        "400": {
                            "description": "Invalid search parameters",
                        },
                    },
                }
            },
        },
    }


def parameter(
    name: str,
    location: str,
    required: bool,
    description: str,
    schema_type: str,
    schema_format: str | None = None,
) -> dict[str, object]:
    schema: dict[str, object] = {"type": schema_type}
    if schema_format:
        schema["format"] = schema_format
    return {
        "name": name,
        "in": location,
        "required": required,
        "description": description,
        "schema": schema,
    }


def render_docs(host: str, port: int) -> str:
    openapi_url = f"http://{host}:{port}/openapi.json"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Tee Time Finder API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({{
        url: "{openapi_url}",
        dom_id: "#swagger-ui"
      }});
    </script>
  </body>
</html>"""


def _read_static_asset(asset_name: str) -> tuple[bytes, str]:
    safe_name = Path(asset_name).name
    asset_path = STATIC_DIR / safe_name
    content_type = {
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }.get(asset_path.suffix, "application/octet-stream")
    return asset_path.read_bytes(), content_type


def _read_static_text(asset_name: str) -> str:
    return (STATIC_DIR / asset_name).read_text()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Tee Time Finder web server.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    run_server(config_path=args.config, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
