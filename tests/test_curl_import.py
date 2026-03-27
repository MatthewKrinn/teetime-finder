import unittest

from tee_time_finder.curl_import import import_curl_to_course_config, parse_curl_command


class CurlImportTests(unittest.TestCase):
    def test_parse_curl_command_extracts_request_parts(self) -> None:
        command = (
            "curl 'https://example.com/api/tee-times?date=2026-03-26' "
            "-H 'Content-Type: application/json' "
            "-H 'Sec-Fetch-Site: same-origin' "
            "--data-raw '{\"courseId\":1172,\"players\":2}'"
        )

        parsed = parse_curl_command(command)

        self.assertEqual(parsed.method, "POST")
        self.assertEqual(parsed.url, "https://example.com/api/tee-times?date=2026-03-26")
        self.assertEqual(parsed.headers["Content-Type"], "application/json")
        self.assertNotIn("Sec-Fetch-Site", parsed.headers)
        self.assertEqual(parsed.body_json, {"courseId": 1172, "players": 2})

    def test_import_curl_to_course_config_applies_replacements(self) -> None:
        command = (
            "curl 'https://example.com/api/tee-times?date=2026-03-26' "
            "-H 'Content-Type: application/json' "
            "--data-raw '{\"courseId\":1172,\"players\":2,\"date\":\"2026-03-26\"}'"
        )

        payload = import_curl_to_course_config(
            curl_command=command,
            course_id="pohick-bay",
            course_name="Pohick Bay",
            provider="teeitup",
            timezone="America/New_York",
            replacements={
                "2026-03-26": "{date}",
                "1172": "{course_vendor_id}",
            },
        )

        course = payload["courses"][0]
        provider_config = course["provider_config"]
        self.assertEqual(course["provider"], "teeitup")
        self.assertEqual(provider_config["endpoint"], "https://example.com/api/tee-times?date={date}")
        self.assertEqual(
            provider_config["body_json"],
            {"courseId": "{course_vendor_id}", "players": 2, "date": "{date}"},
        )

    def test_import_curl_to_course_config_uses_response_mapping_inference(self) -> None:
        command = (
            "curl 'https://example.com/api/tee-times?date=2026-03-26' "
            "-H 'Content-Type: application/json' "
            "--data-raw '{\"courseId\":1172,\"players\":2,\"date\":\"2026-03-26\"}'"
        )
        response_payload = {
            "results": [
                {
                    "teeDate": "2026-03-26",
                    "teeTime": "07:10",
                    "rates": [{"amount": "40.75"}],
                    "availability": {"availablePlayers": 4},
                    "links": {"book": "https://example.com/slot/1"},
                }
            ]
        }

        payload = import_curl_to_course_config(
            curl_command=command,
            course_id="pohick-bay",
            course_name="Pohick Bay",
            provider="teeitup",
            timezone="America/New_York",
            response_payload=response_payload,
        )

        provider_config = payload["courses"][0]["provider_config"]
        self.assertEqual(provider_config["items_path"], "results")
        self.assertEqual(provider_config["date_field"], "teeDate")
        self.assertEqual(provider_config["time_field"], "teeTime")
        self.assertEqual(provider_config["price_field"], "rates.0.amount")
        self.assertEqual(provider_config["available_players_field"], "availability.availablePlayers")
        self.assertEqual(provider_config["booking_url_field"], "links.book")
        self.assertNotIn("starts_at_field", provider_config)


if __name__ == "__main__":
    unittest.main()
