# Tee Time Finder

`tee_time_finder` is a Python app for searching live golf tee times across multiple booking providers from one place.

## Use The UI

Most people should start here.

From the project root:

```bash
uv sync
uv run tee-time-finder serve --config configs/live.json --port 8080
```

Then open:

- `http://127.0.0.1:8080/` for the web UI
- `http://127.0.0.1:8080/docs` for Swagger UI
- `http://127.0.0.1:8080/openapi.json` for the raw OpenAPI document

In the UI you can:

- choose a time window with the dual slider
- choose `9`, `18`, or `Either`
- turn course groups on or off
- fine-tune individual courses inside each group

Notes:

- Results are live snapshots. A tee time can disappear or sell out right after it is returned.
- The response includes `retrieved_at` so you can see when the data was fetched.
- If you change a config file while the server is running, restart the server.

## Quick Commands

List all configured courses:

```bash
uv run tee-time-finder list-courses --config configs/live.json
```

Search everything from the CLI:

```bash
uv run tee-time-finder search \
  --config configs/live.json \
  --date 2026-03-27 \
  --players 2 \
  --earliest 12:00 \
  --latest 16:00 \
  --json
```

Search a single provider family:

```bash
uv run tee-time-finder search --config configs/mcg.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/pohick.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/fairfax.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/enterprise.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/umd.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
```

Run tests:

```bash
uv run python -m unittest discover -s tests -v
```

## Config Files

Configs live in `configs/`.

- `configs/live.json`: all live providers currently wired into the app
- `configs/mcg.json`: Montgomery County / TenFore
- `configs/pohick.json`: Pohick Bay / TeeItUp
- `configs/fairfax.json`: Fairfax County / TeeItUp
- `configs/enterprise.json`: Enterprise Golf Course / TeeItUp
- `configs/umd.json`: University of Maryland / Chronogolf
- `configs/starter.json`: mixed starter file, including placeholders that are not all live yet

## uv Workflow

Typical commands:

```bash
uv sync
uv run tee-time-finder serve --config configs/live.json --port 8080
uv run tee-time-finder list-courses --config configs/live.json
uv run tee-time-finder search --config configs/live.json --date 2026-03-27 --players 2
uv run python -m unittest discover -s tests -v
uv lock
```

## Course Config Format

Each config file contains a `courses` list. Every course has:

- `id`
- `name`
- `provider`
- `group`
- `timezone`
- `booking_url`
- `provider_config`

Example:

```json
{
  "courses": [
    {
      "id": "falls-road-tenfore",
      "name": "Falls Road Golf Course",
      "provider": "tenfore",
      "group": "MCG",
      "timezone": "America/New_York",
      "booking_url": "https://fox.tenfore.golf/fallsroad",
      "provider_config": {
        "golf_course_id": 16503,
        "vanity_name": "fallsroad",
        "default_holes": 18,
        "prefer_holes": 18,
        "booking_url_template": "https://fox.tenfore.golf/{vanity_name}"
      }
    }
  ]
}
```

## Supported Providers

### `tenfore`

Dedicated live adapter for TenFore-backed sites like `fox.tenfore.golf/mcggolf`.

Useful config keys:

- `golf_course_id`: required
- `sub_course_id`: optional sub-course id for alternate 9-hole loops
- `vanity_name`: optional vanity path used for click-through URLs
- `api_url`: optional backend base URL, default `https://swan.tenfore.golf/api`
- `app_id`: optional, default `71`
- `default_holes`: optional default hole count
- `prefer_holes`: optional hole count to prefer when both 9 and 18 exist
- `booking_url_template`: optional click-through URL template

Runnable example: `configs/mcg.json`

### `teeitup`

Dedicated live adapter for Kenna/TeeItUp-backed sites like `nova-parks.book.teeitup.com`.

Useful config keys:

- `alias`: required value sent as the `x-be-alias` header
- `facility_id`: required facility id
- `be_api_url`: optional backend base URL, default `https://phx-api-be-east-1b.kenna.io`
- `prefer_holes`: optional hole count to prefer
- `promotion_code`: optional promotion code
- `customer_id`: optional customer id
- `return_promoted_rates`: optional boolean
- `date_max`: optional range-search upper bound
- `booking_url_template`: optional click-through URL template

Runnable examples:

- `configs/pohick.json`
- `configs/fairfax.json`
- `configs/enterprise.json`

### `chronogolf`

Dedicated live adapter for Chronogolf clubs using the official widget-style tee-time feed.

Useful config keys:

- `club_id`: required Chronogolf club id
- `course_id`: required course id used by the widget endpoint
- `affiliation_type_id`: required affiliation type id, repeated per requested player
- `club_slug`: optional slug for booking links
- `supported_holes`: optional hole list to query when the user picks `Either`
- `rate_name`: optional fixed label such as `Guest`
- `marketplace_base_url`: optional base URL, default `https://www.chronogolf.com/marketplace`
- `headers`: optional extra request headers
- `booking_url_template`: optional click-through URL template

Runnable example: `configs/umd.json`

### `json_api`

Generic adapter for providers that expose tee times in JSON.

Useful config keys:

- `endpoint`
- `method`
- `headers`
- `query_params`
- `variables`
- `body_json`
- `body_text`
- `items_path`
- `starts_at_field`
- `time_field`
- `date_field`
- `price_field`
- `price_min_field`
- `price_max_field`
- `holes_field`
- `hole_options_field`
- `rate_name_field`
- `player_options_field`
- `min_players_field`
- `max_players_field`
- `available_players_field`
- `booking_url_field`
- `booking_url_template`

### `html_regex`

Simple adapter for server-rendered pages where tee times can be extracted from HTML with a regex.

Useful config keys:

- `endpoint`
- `headers`
- `slot_pattern`
- `date`

Optional named regex groups:

- `time`
- `price`
- `players`
- `url`

### `golfnow`

This is still the least-finished provider path in the project. Right now it works best when you capture a real browser request and use `import-curl` to build a recipe for that specific course.

## Adding A New Course

If the course uses an existing provider:

1. Add a new course entry to a config file in `configs/`.
2. Set `provider` to the right adapter.
3. Fill in the provider-specific `provider_config`.
4. Restart the server if the UI is already running.

If the course needs a new provider:

1. Add a new provider module in `src/tee_time_finder/providers/`.
2. Subclass `BookingProvider`.
3. Implement `search(course, request, http_client)`.
4. Register it in `provider_registry`.

## Importing A Captured Request

For dynamic booking sites that do not already have a dedicated adapter, the fastest path is usually:

1. Open the booking page in your browser.
2. Copy the tee-time request as cURL.
3. Run `import-curl`.
4. Fill in the response mapping fields.

Example:

```bash
uv run tee-time-finder import-curl \
  --curl-file request.txt \
  --course-id new-course \
  --course-name "New Course" \
  --provider json_api
```

This is a setup step, not the normal day-to-day workflow. Once a course is configured, the app becomes the catch-all search layer and you should not need to visit each booking site manually.

## License

This project is proprietary and all rights are reserved. See `LICENSE`.
