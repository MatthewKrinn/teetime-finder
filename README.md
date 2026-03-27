# Tee Time Finder

`tee_time_finder` is a Python app for searching golf tee times across multiple booking providers from one place.

The first version focuses on three goals:

- Normalize tee time results into one shared format.
- Keep provider-specific logic isolated in adapters.
- Make it simple to add courses through JSON config.
- Stay API-first so you can use CLI tooling and Swagger docs before investing in custom UI work.
- Treat provider data as a live snapshot that may change immediately after retrieval.

## What is included

- A shared search model for date, time window, and player count.
- A provider registry with pluggable provider adapters.
- Live provider adapters for currently supported TenFore and TeeItUp sites.
- Generic JSON and HTML/regex providers for simple integrations.
- Request-recipe support for replaying real browser API calls from dynamic booking sites.
- A CLI for local searching.
- A lightweight local web UI plus JSON API and OpenAPI/Swagger docs.
- Freshness metadata and no-cache API responses for volatile tee-time data.

## Quick Start

From the project root:

```bash
uv sync
uv run tee-time-finder list-courses --config configs/live.json
uv run tee-time-finder search --config configs/live.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/enterprise.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/umd.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/pohick.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/fairfax.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder search --config configs/mcg.json --date 2026-03-27 --players 2 --earliest 12:00 --latest 16:00 --json
uv run tee-time-finder import-curl --curl-file request.txt --course-id pohick-bay --course-name "Pohick Bay" --provider teeitup
uv run tee-time-finder serve --config configs/live.json --port 8080
```

Then open:

- `http://127.0.0.1:8080/` for the web UI
- `http://127.0.0.1:8080/openapi.json` for the raw OpenAPI document
- `http://127.0.0.1:8080/docs` for Swagger UI docs
- `http://127.0.0.1:8080/api/search?date=2026-03-27&players=2&earliest=07:00&latest=11:30` for direct JSON search results

Each result is a live snapshot and includes `retrieved_at`. Tee times can disappear or sell out after the response is returned.

The web UI supports:

- a dual-handle time window slider
- 9-hole, 18-hole, or either filtering
- grouped course controls so you can turn a whole family like MCG on or off, then fine-tune individual courses

## uv Workflow

This project is set up to be used with `uv`.

Typical commands:

```bash
uv sync
uv run tee-time-finder list-courses --config configs/live.json
uv run tee-time-finder search --config configs/live.json --date 2026-03-27 --players 2
uv run python -m unittest discover -s tests -v
uv lock
```

If `uv` is not installed yet, install it first and then run `uv sync`. The first `uv sync` or `uv run` will create `uv.lock`; that file should be checked into version control.

## Course Config

Course configs live in `configs/`. Each course points to a `provider` and a provider-specific `provider_config`.

Example:

```json
{
  "courses": [
    {
      "id": "falls-road-tenfore",
      "name": "Falls Road Golf Course",
      "provider": "tenfore",
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

## Provider Types

### `json_api`

Useful when a provider exposes tee times in JSON.

Supported config keys:

- `endpoint`: URL template, such as `https://example.com/api/tee-times?date={date}&players={players}`
- `method`: `GET` or `POST`
- `headers`: optional HTTP headers with template values
- `query_params`: optional query params added after template rendering
- `variables`: optional provider-specific values used in templates
- `body_json`: optional JSON body template for `POST` requests
- `body_text`: optional raw text body template
- `items_path`: dot path to the list of tee time items
- `starts_at_field`: optional field containing a full datetime
- `time_field`: field name or dot path within each item
- `date_field`: optional field name or dot path if the date lives on the item
- `price_field`: optional field name or dot path
- `price_min_field`: optional field name or dot path for minimum price
- `price_max_field`: optional field name or dot path for maximum price
- `holes_field`: optional field name or dot path
- `hole_options_field`: optional field name or dot path containing a list of hole options
- `rate_name_field`: optional field name or dot path
- `player_options_field`: optional field name or dot path containing a list of player-count options
- `min_players_field`: optional field name or dot path for minimum player count
- `max_players_field`: optional field name or dot path for maximum player count
- `available_players_field`: optional field name or dot path
- `booking_url_field`: optional field name or dot path
- `booking_url_template`: optional URL template using item keys

### `html_regex`

Useful for simple server-rendered pages when tee times are in HTML.

Supported config keys:

- `endpoint`: URL template
- `headers`: optional HTTP headers
- `slot_pattern`: regex with a required named group `time`
- `date`: optional fixed date override

Optional named groups in the regex:

- `price`
- `players`
- `url`

### `tenfore`, `teeitup`, `chronogolf`, `golfnow`

These are named site-family adapters for real-world golf booking ecosystems. `tenfore` and `teeitup` have dedicated live adapters described below. `chronogolf` is a named config path for Chronogolf marketplace JSON responses. `golfnow` still works best when you point it at a real browser-captured request recipe and then fill in the response mapping fields.

That gives you a cleaner mental model:

- `provider` answers "which booking family is this course on?"
- `provider_config` answers "what request does this specific course use, and how do I parse the response?"

Starter templates for real sites live in `configs/starter.json`.

### `tenfore` live mode

`tenfore` now has a dedicated live adapter for TenFore-backed sites like `fox.tenfore.golf/mcggolf`.

Supported live config keys:

- `golf_course_id`: required TenFore course id, such as `16503`
- `sub_course_id`: optional sub-course id for 9-hole variants, such as `1032`
- `vanity_name`: optional booking vanity used to build a click-through URL
- `api_url`: optional backend base URL. Defaults to `https://swan.tenfore.golf/api`
- `app_id`: optional TenFore app id. Defaults to `71`
- `default_holes`: optional default hole count for rate selection
- `prefer_holes`: optional hole count to prefer when both 9- and 18-hole prices exist
- `booking_url_template`: optional booking page URL template

Example:

```json
{
  "id": "falls-road-tenfore",
  "name": "Falls Road Golf Course",
  "provider": "tenfore",
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
```

That config is ready to run today in `configs/mcg.json`.

Adding another TenFore course is usually just a new JSON entry with:

- `id`
- `name`
- `booking_url`
- `provider_config.golf_course_id`

If the course exposes a distinct 9-hole loop, you can add another entry with the same `golf_course_id` plus a `sub_course_id`.

### `teeitup` live mode

`teeitup` now has a dedicated live adapter for Kenna/TeeItUp-backed sites like `nova-parks.book.teeitup.com`.

Supported live config keys:

- `alias`: required value sent as the `x-be-alias` header, such as `nova-parks`
- `facility_id`: required TeeItUp facility id, such as `1172`
- `be_api_url`: optional backend base URL. Defaults to `https://phx-api-be-east-1b.kenna.io`
- `prefer_holes`: optional hole count to prefer when a tee time exposes multiple rates
- `promotion_code`: optional promotion code query parameter
- `customer_id`: optional customer id query parameter
- `return_promoted_rates`: optional boolean query parameter
- `date_max`: optional TeeItUp range-search upper bound
- `booking_url_template`: optional booking page URL template

Example:

```json
{
  "id": "pohick-bay-teeitup",
  "name": "Pohick Bay Regional Golf Course (TeeItUp)",
  "provider": "teeitup",
  "timezone": "America/New_York",
  "booking_url": "https://nova-parks.book.teeitup.com/?course=1172&date={date}&max=999999&utm_campaign=reserve&utm_medium=organic",
  "provider_config": {
    "alias": "nova-parks",
    "be_api_url": "https://phx-api-be-east-1b.kenna.io",
    "facility_id": 1172,
    "prefer_holes": 18,
    "booking_url_template": "https://nova-parks.book.teeitup.com/?course={facility_id}&date={date}&max=999999&utm_campaign=reserve&utm_medium=organic"
  }
}
```

That config is ready to run today in `configs/pohick.json`.

If you want to use the mixed starter file before the other providers are wired, search with `--course-id pohick-bay-teeitup` so only the live TeeItUp entry is queried.

To add another course on the same TeeItUp hostname, you usually reuse the same `alias` and `be_api_url` and only change:

- `id`
- `name`
- `booking_url`
- `provider_config.facility_id`

`configs/fairfax.json` shows that pattern for Fairfax County's Laurel Hill (`4595`) and Burke Lake (`3485`) courses.

`configs/enterprise.json` is a runnable one-course example for Enterprise Golf Course (`7790`) on the `pg-parks-rec` TeeItUp host.

### `chronogolf` config pattern

`chronogolf` is currently backed by the shared JSON API adapter, but it is exposed as its own provider name so Chronogolf courses are easy to identify in configs and in the UI.

Typical config fields:

- `endpoint`: Chronogolf marketplace tee-time endpoint
- `headers`: set a browser-like `User-Agent` such as `Mozilla/5.0`, because Chronogolf rejects the default Python `urllib` user agent
- `variables.course_uuid`: the course UUID used in `course_ids`
- `price_field`: usually `default_price.subtotal`
- `hole_options_field`: usually `course.bookable_holes`
- `min_players_field` and `max_players_field`: usually `min_player_size` and `max_player_size`
- `available_players_field`: usually `max_player_size`
- `booking_url_template`: optional deep link into the Chronogolf tee-time options step

`configs/umd.json` is a runnable one-course example for University of Maryland Golf Course.

## Adding A New Course

If the course uses an existing provider adapter:

1. Add a new course entry to your JSON config.
2. Set `provider` to an existing adapter.
3. Fill in `provider_config` with the endpoint and parsing fields.

If the course needs a new provider:

1. Create a new file in `src/tee_time_finder/providers/`.
2. Subclass `BookingProvider`.
3. Implement `search(course, request, http_client)`.
4. Register the provider in `provider_registry`.

## Notes On Real Booking Sites

The app's job is still to be your catch-all search layer.

You should not need to manually visit every booking site each time you want to play. The manual request-capture work below is only a setup step so the app can learn how each provider fetches tee times for a given course or site family. Once that course is configured, your normal workflow is just:

1. Run one CLI/API search.
2. Let the app query every configured provider for you.
3. Compare all matching tee times in one normalized result set.

Many golf booking services render tee times from browser API calls rather than the initial HTML. Because of that, the fastest way to support a new site is usually:

1. Open the booking page in your browser.
2. Inspect the network requests used to load tee times.
3. Copy the tee-time request as cURL from the browser.
4. Run `tee-time-finder import-curl` to generate a config skeleton.
5. Fill in `items_path`, `starts_at_field` or `time_field`, `price_field`, and `available_players_field`.

That approach is usually much simpler, lighter, and more reliable than full browser automation for dynamic booking sites, and it is meant for one-time onboarding per course/provider integration, not for day-to-day searching.

TenFore and TeeItUp are the first exceptions here: for supported sites on those booking families, you can skip manual request capture and use the dedicated live `tenfore` or `teeitup` provider config directly.

Example:

```bash
uv run tee-time-finder import-curl \
  --curl-file request.txt \
  --course-id pohick-bay-teeitup \
  --course-name "Pohick Bay Regional Golf Course" \
  --provider teeitup \
  --replace '2026-03-26={date}' \
  --replace '1172={course_vendor_id}'
```

That command gives you a ready-to-edit config skeleton with:

- the real request URL
- the request method
- the useful headers
- the JSON body, if the browser call used one
- placeholder response mapping fields you can fill in once you inspect the JSON

## Current Targets

The project now includes starter config entries for:

- Montgomery County Golf courses hosted on `fox.tenfore.golf/mcggolf`
- Pohick Bay via `nova-parks.book.teeitup.com` with a live TeeItUp adapter
- Fairfax County TeeItUp courses including Laurel Hill and Burke Lake
- Pohick Bay via GolfNow

`configs/live.json`, `configs/mcg.json`, `configs/pohick.json`, `configs/fairfax.json`, `configs/enterprise.json`, and `configs/umd.json` are runnable real-provider examples. `configs/starter.json` is still the mixed onboarding file, so its GolfNow entry remains a placeholder until we capture that request/response shape.
