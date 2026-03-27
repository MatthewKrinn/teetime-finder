from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from tee_time_finder.config import load_courses
from tee_time_finder.curl_import import import_curl_to_course_config
from tee_time_finder.models import SearchRequest
from tee_time_finder.service import TeeTimeService
from tee_time_finder.utils import parse_time


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search golf tee times across providers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-courses", help="List configured courses")
    list_parser.add_argument("--config", required=True, help="Path to a course config JSON file")

    search_parser = subparsers.add_parser("search", help="Search for tee times")
    search_parser.add_argument("--config", required=True, help="Path to a course config JSON file")
    search_parser.add_argument("--date", required=True, help="Search date in YYYY-MM-DD format")
    search_parser.add_argument("--players", required=True, type=int, help="Required player count")
    search_parser.add_argument("--earliest", help="Earliest tee time in HH:MM format")
    search_parser.add_argument("--latest", help="Latest tee time in HH:MM format")
    search_parser.add_argument(
        "--course-id",
        action="append",
        dest="course_ids",
        help="Limit results to one or more course ids",
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a text table",
    )

    import_parser = subparsers.add_parser(
        "import-curl",
        help="Generate a course config skeleton from a copied browser curl command",
    )
    import_parser.add_argument("--curl-file", required=True, help="Path to a text file containing a curl command")
    import_parser.add_argument("--course-id", required=True)
    import_parser.add_argument("--course-name", required=True)
    import_parser.add_argument("--provider", default="json_api")
    import_parser.add_argument("--booking-url")
    import_parser.add_argument("--timezone", default="America/New_York")
    import_parser.add_argument("--response-file", help="Optional sample JSON response to infer field mappings")
    import_parser.add_argument("--output", help="Optional path to write the generated config JSON")
    import_parser.add_argument(
        "--replace",
        action="append",
        default=[],
        help="Literal replacement in OLD=NEW form, e.g. 2026-03-26={date}",
    )

    serve_parser = subparsers.add_parser("serve", help="Run the local web UI")
    serve_parser.add_argument("--config", required=True, help="Path to a course config JSON file")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        from tee_time_finder.web import run_server

        run_server(config_path=args.config, host=args.host, port=args.port)
        return

    if args.command == "import-curl":
        curl_command = Path(args.curl_file).read_text()
        replacements = parse_replacements(args.replace)
        response_payload = None
        if args.response_file:
            response_payload = json.loads(Path(args.response_file).read_text())
        payload = import_curl_to_course_config(
            curl_command=curl_command,
            course_id=args.course_id,
            course_name=args.course_name,
            provider=args.provider,
            timezone=args.timezone,
            booking_url=args.booking_url,
            replacements=replacements,
            response_payload=response_payload,
        )
        rendered = json.dumps(payload, indent=2)
        if args.output:
            Path(args.output).write_text(rendered + "\n")
            print(f"Wrote generated config to {args.output}")
            return
        print(rendered)
        return

    courses = load_courses(args.config)
    service = TeeTimeService(courses)

    if args.command == "list-courses":
        for course in service.list_courses():
            print(f"{course.id}\t{course.name}\t[{course.provider}]")
        return

    request = SearchRequest(
        date=date.fromisoformat(args.date),
        players=args.players,
        earliest=parse_time(args.earliest) if args.earliest else None,
        latest=parse_time(args.latest) if args.latest else None,
        course_ids=set(args.course_ids) if args.course_ids else None,
    )
    results = service.search(request)
    if args.json:
        payload = [
            {
                "course_id": item.course_id,
                "course_name": item.course_name,
                "provider": item.provider,
                "starts_at": item.starts_at.isoformat(),
                "retrieved_at": item.retrieved_at.isoformat(),
                "available_players": item.available_players,
                "price": item.price,
                "holes": item.holes,
                "rate_name": item.rate_name,
                "booking_url": item.booking_url,
            }
            for item in results
        ]
        print(json.dumps(payload, indent=2))
        return

    print_table(results)


def print_table(results: list) -> None:
    if not results:
        print("No tee times found.")
        return
    retrieved_at = max(item.retrieved_at for item in results)
    print(
        "Live snapshot fetched at "
        f"{retrieved_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}. "
        "Availability can change after this search."
    )
    headers = ("Course", "Start", "Holes", "Players", "Price", "Provider")
    rows = [
        (
            item.course_name,
            item.starts_at.strftime("%Y-%m-%d %H:%M"),
            str(item.holes) if item.holes is not None else "-",
            str(item.available_players) if item.available_players is not None else "-",
            f"${item.price:.2f}" if item.price is not None else "-",
            item.provider,
        )
        for item in results
    ]
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]
    print("  ".join(cell.ljust(width) for cell, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)))


def parse_replacements(values: list[str]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid replacement '{value}'. Expected OLD=NEW.")
        old, new = value.split("=", 1)
        replacements[old] = new
    return replacements


if __name__ == "__main__":
    main()
