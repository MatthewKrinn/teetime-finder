import unittest
from datetime import date
import json

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest
from tee_time_finder.service import TeeTimeService


class StubHttpClient(HttpClient):
    def __init__(
        self,
        payload: object | None = None,
        payload_by_url: dict[str, object] | None = None,
    ) -> None:
        self.requests: list[dict[str, object]] = []
        self.payload = payload or {
            "results": [
                {
                    "startsAt": "2026-03-27T07:10:00",
                    "price": "40.75",
                    "availablePlayers": 4,
                    "bookingUrl": "https://example.com/slot/1",
                }
            ]
        }
        self.payload_by_url = payload_by_url or {}

    def request_json(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | bytes | None = None,
    ) -> object:
        self.requests.append(
            {
                "url": url,
                "method": method,
                "headers": headers or {},
                "body": body,
            }
        )
        if url in self.payload_by_url:
            return self.payload_by_url[url]
        return self.payload


class TeeTimeServiceTests(unittest.TestCase):
    def test_service_filters_by_time_and_players(self) -> None:
        course = CourseDefinition(
            id="json-course",
            name="JSON Course",
            provider="json_api",
            provider_config={
                "endpoint": "https://example.com/api/search",
                "items_path": "results",
                "starts_at_field": "startsAt",
                "price_field": "price",
                "available_players_field": "availablePlayers",
            },
        )
        http_client = StubHttpClient(
            payload={
                "results": [
                    {
                        "startsAt": "2026-03-27T07:10:00",
                        "price": 50,
                        "availablePlayers": 4,
                    },
                    {
                        "startsAt": "2026-03-27T12:15:00",
                        "price": 65,
                        "availablePlayers": 1,
                    },
                ]
            }
        )
        service = TeeTimeService([course], http_client=http_client)
        request = SearchRequest(
            date=date.fromisoformat("2026-03-27"),
            players=2,
        )
        results = service.search(request)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].starts_at.strftime("%H:%M"), "07:10")
        self.assertIsNotNone(results[0].retrieved_at)

    def test_json_api_provider_supports_post_body_and_starts_at_field(self) -> None:
        course = CourseDefinition(
            id="pohick-json",
            name="Pohick JSON",
            provider="json_api",
            provider_config={
                "endpoint": "https://example.com/api/search",
                "method": "POST",
                "headers": {
                    "Content-Type": "application/json",
                    "X-Course": "{course_vendor_id}",
                },
                "variables": {
                    "course_vendor_id": 1172,
                },
                "body_json": {
                    "courseId": "{course_vendor_id}",
                    "date": "{date}",
                    "players": "{players}",
                },
                "items_path": "results",
                "starts_at_field": "startsAt",
                "price_field": "price",
                "available_players_field": "availablePlayers",
                "booking_url_field": "bookingUrl",
            },
        )
        http_client = StubHttpClient()
        service = TeeTimeService([course], http_client=http_client)
        request = SearchRequest(
            date=date.fromisoformat("2026-03-27"),
            players=2,
        )

        results = service.search(request)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].price, 40.75)
        self.assertEqual(len(http_client.requests), 1)
        recorded_request = http_client.requests[0]
        self.assertEqual(recorded_request["method"], "POST")
        self.assertEqual(recorded_request["headers"]["X-Course"], "1172")
        self.assertEqual(
            json.loads(recorded_request["body"]),
            {"courseId": 1172, "date": "2026-03-27", "players": 2},
        )

    def test_json_api_provider_supports_nested_paths_and_list_indexes(self) -> None:
        course = CourseDefinition(
            id="pohick-nested",
            name="Pohick Nested",
            provider="json_api",
            provider_config={
                "endpoint": "https://example.com/api/search",
                "items_path": "results",
                "starts_at_field": "slot.startsAt",
                "price_field": "pricing.offers.0.amount",
                "available_players_field": "availability.availablePlayers",
                "booking_url_field": "pricing.offers.0.bookingUrl",
            },
        )
        payload = {
            "results": [
                {
                    "slot": {"startsAt": "2026-03-27T07:10:00"},
                    "pricing": {
                        "offers": [
                            {
                                "amount": "40.75",
                                "bookingUrl": "https://example.com/slot/1",
                            }
                        ]
                    },
                    "availability": {"availablePlayers": 4},
                }
            ]
        }
        http_client = StubHttpClient(payload=payload)
        service = TeeTimeService([course], http_client=http_client)
        request = SearchRequest(
            date=date.fromisoformat("2026-03-27"),
            players=2,
        )

        results = service.search(request)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].price, 40.75)
        self.assertEqual(results[0].booking_url, "https://example.com/slot/1")

    def test_service_can_filter_by_holes(self) -> None:
        course = CourseDefinition(
            id="json-course",
            name="JSON Course",
            provider="json_api",
            provider_config={
                "endpoint": "https://example.com/api/search",
                "items_path": "results",
                "starts_at_field": "startsAt",
                "price_field": "price",
                "holes_field": "holes",
                "available_players_field": "availablePlayers",
            },
        )
        http_client = StubHttpClient(
            payload={
                "results": [
                    {
                        "startsAt": "2026-03-27T12:05:00",
                        "price": 55,
                        "holes": 9,
                        "availablePlayers": 4,
                    },
                    {
                        "startsAt": "2026-03-27T12:10:00",
                        "price": 72,
                        "holes": 18,
                        "availablePlayers": 4,
                    },
                ]
            }
        )
        service = TeeTimeService([course], http_client=http_client)

        results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=2,
                holes=18,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].holes, 18)
        self.assertEqual(results[0].price, 72)

    def test_chronogolf_provider_alias_supports_marketplace_response(self) -> None:
        course = CourseDefinition(
            id="umd-chronogolf",
            name="University of Maryland Golf Course",
            provider="chronogolf",
            provider_config={
                "endpoint": "https://www.chronogolf.com/marketplace/v2/teetimes?start_date={date}&course_ids={course_uuid}&holes=9,18&free_slots={players}&page=1",
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
                "variables": {
                    "course_uuid": "617d2a87-3ddc-4b68-a75c-fcbddb74ca22",
                    "club_slug": "university-of-maryland-golf-club",
                },
                "items_path": "teetimes",
                "starts_at_field": "starts_at",
                "price_field": "default_price.subtotal",
                "hole_options_field": "course.bookable_holes",
                "rate_name_field": "default_price.affiliation_type",
                "min_players_field": "min_player_size",
                "max_players_field": "max_player_size",
                "available_players_field": "max_player_size",
                "booking_url_template": "https://www.chronogolf.com/club/{club_slug}?date={date}&step=options&teetime={uuid}",
            },
        )
        payload = {
            "status": "open",
            "teetimes": [
                {
                    "uuid": "2f8d0c43-6567-4a9b-8f51-4150cf734949",
                    "starts_at": "2026-03-27T12:20:00Z",
                    "min_player_size": 2,
                    "max_player_size": 4,
                    "course": {"bookable_holes": [9, 18]},
                    "default_price": {
                        "subtotal": 57.0,
                        "affiliation_type": "Guest",
                    },
                }
            ],
        }
        http_client = StubHttpClient(payload=payload)
        service = TeeTimeService([course], http_client=http_client)

        results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=2,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].price, 57.0)
        self.assertIsNone(results[0].holes)
        self.assertEqual(results[0].hole_options, (9, 18))
        self.assertEqual(results[0].player_options, (2, 3, 4))
        self.assertEqual(results[0].rate_name, "Guest")
        self.assertEqual(results[0].available_players, 4)
        self.assertEqual(
            results[0].booking_url,
            "https://www.chronogolf.com/club/university-of-maryland-golf-club?date=2026-03-27&step=options&teetime=2f8d0c43-6567-4a9b-8f51-4150cf734949",
        )
        self.assertEqual(http_client.requests[0]["headers"]["Accept"], "application/json")
        self.assertEqual(http_client.requests[0]["headers"]["User-Agent"], "Mozilla/5.0")

    def test_chronogolf_provider_uses_widget_endpoint_for_legacy_booking_feed(self) -> None:
        course = CourseDefinition(
            id="umd-chronogolf",
            name="University of Maryland Golf Course",
            provider="chronogolf",
            booking_url="https://www.chronogolf.com/club/university-of-maryland-golf-club?date={date}",
            provider_config={
                "club_id": 7630,
                "course_id": 8701,
                "club_slug": "university-of-maryland-golf-club",
                "affiliation_type_id": 31342,
                "supported_holes": [9, 18],
            },
        )
        http_client = StubHttpClient(
            payload_by_url={
                "https://www.chronogolf.com/marketplace/clubs/7630/teetimes?date=2026-03-27&course_id=8701&affiliation_type_ids=31342%2C31342%2C31342&nb_holes=18": [
                    {
                        "id": 1001,
                        "uuid": "legacy-18-0840",
                        "date": "2026-03-27",
                        "start_time": "08:40",
                        "out_of_capacity": False,
                        "frozen": False,
                        "green_fees": [
                            {"subtotal": 80.0, "affiliation_type_name": "Guest"},
                            {"subtotal": 80.0, "affiliation_type_name": "Guest"},
                            {"subtotal": 80.0, "affiliation_type_name": "Guest"},
                        ],
                    }
                ]
            }
        )
        service = TeeTimeService([course], http_client=http_client)

        results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=3,
                earliest=None,
                latest=None,
                holes=18,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].starts_at.strftime("%H:%M"), "08:40")
        self.assertEqual(results[0].holes, 18)
        self.assertEqual(results[0].hole_options, (18,))
        self.assertEqual(results[0].price, 80.0)
        self.assertEqual(results[0].player_options, (3,))
        self.assertEqual(results[0].available_players, 3)
        self.assertEqual(results[0].rate_name, "Guest")
        self.assertEqual(
            http_client.requests[0]["url"],
            "https://www.chronogolf.com/marketplace/clubs/7630/teetimes?date=2026-03-27&course_id=8701&affiliation_type_ids=31342%2C31342%2C31342&nb_holes=18",
        )
        self.assertEqual(http_client.requests[0]["headers"]["Accept"], "application/json")
        self.assertEqual(http_client.requests[0]["headers"]["User-Agent"], "Mozilla/5.0")

    def test_chronogolf_provider_merges_9_and_18_hole_widget_rows(self) -> None:
        course = CourseDefinition(
            id="umd-chronogolf",
            name="University of Maryland Golf Course",
            provider="chronogolf",
            booking_url="https://www.chronogolf.com/club/university-of-maryland-golf-club?date={date}",
            provider_config={
                "club_id": 7630,
                "course_id": 8701,
                "club_slug": "university-of-maryland-golf-club",
                "affiliation_type_id": 31342,
                "supported_holes": [9, 18],
            },
        )
        http_client = StubHttpClient(
            payload_by_url={
                "https://www.chronogolf.com/marketplace/clubs/7630/teetimes?date=2026-03-27&course_id=8701&affiliation_type_ids=31342%2C31342&nb_holes=9": [
                    {
                        "id": 1002,
                        "uuid": "legacy-9-0820",
                        "date": "2026-03-27",
                        "start_time": "08:20",
                        "out_of_capacity": False,
                        "frozen": False,
                        "green_fees": [
                            {"subtotal": 57.0, "affiliation_type_name": "Guest"},
                            {"subtotal": 57.0, "affiliation_type_name": "Guest"},
                        ],
                    }
                ],
                "https://www.chronogolf.com/marketplace/clubs/7630/teetimes?date=2026-03-27&course_id=8701&affiliation_type_ids=31342%2C31342&nb_holes=18": [
                    {
                        "id": 1003,
                        "uuid": "legacy-18-0820",
                        "date": "2026-03-27",
                        "start_time": "08:20",
                        "out_of_capacity": False,
                        "frozen": False,
                        "green_fees": [
                            {"subtotal": 80.0, "affiliation_type_name": "Guest"},
                            {"subtotal": 80.0, "affiliation_type_name": "Guest"},
                        ],
                    }
                ],
            }
        )
        service = TeeTimeService([course], http_client=http_client)

        results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=2,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].starts_at.strftime("%H:%M"), "08:20")
        self.assertIsNone(results[0].holes)
        self.assertEqual(results[0].hole_options, (9, 18))
        self.assertEqual(results[0].price, 57.0)
        self.assertEqual(results[0].price_min, 57.0)
        self.assertEqual(results[0].price_max, 80.0)
        self.assertEqual(results[0].player_options, (2,))
        self.assertEqual(results[0].available_players, 2)
        self.assertEqual(len(http_client.requests), 2)

    def test_tenfore_provider_queries_live_style_endpoint_and_selects_18_hole_rate(self) -> None:
        course = CourseDefinition(
            id="falls-road-tenfore",
            name="Falls Road Golf Course",
            provider="tenfore",
            timezone="America/New_York",
            booking_url="https://fox.tenfore.golf/fallsroad",
            provider_config={
                "golf_course_id": 16503,
                "vanity_name": "fallsroad",
                "default_holes": 18,
            },
        )
        payload = {
            "successful": True,
            "data": [
                {
                    "id": 5206390,
                    "date": "2026-03-27",
                    "time": "12:10:00",
                    "spots": 4,
                    "feeTitle": "Public",
                    "fullPrice18": 64.0,
                    "feePrice18": 64.0,
                    "fullPrice9": 28.0,
                    "feePrice9": 28.0,
                }
            ],
        }
        http_client = StubHttpClient(payload=payload)
        service = TeeTimeService([course], http_client=http_client)
        request = SearchRequest(
            date=date.fromisoformat("2026-03-27"),
            players=2,
        )

        results = service.search(request)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].starts_at.strftime("%Y-%m-%d %H:%M"), "2026-03-27 12:10")
        self.assertEqual(results[0].price, 64.0)
        self.assertEqual(results[0].holes, 18)
        self.assertEqual(results[0].rate_name, "Public")
        self.assertEqual(results[0].booking_url, "https://fox.tenfore.golf/fallsroad")
        self.assertEqual(len(http_client.requests), 1)
        recorded_request = http_client.requests[0]
        self.assertEqual(
            recorded_request["url"],
            "https://swan.tenfore.golf/api/BookingEngineV4/booking-times",
        )
        self.assertEqual(recorded_request["method"], "POST")
        self.assertEqual(recorded_request["headers"]["Content-Type"], "application/json")
        self.assertEqual(
            json.loads(recorded_request["body"]),
            {
                "golfCourseId": 16503,
                "subCourseId": None,
                "dateFrom": "2026-03-27",
                "appId": 71,
            },
        )

    def test_tenfore_provider_supports_sub_course_and_9_hole_selection(self) -> None:
        course = CourseDefinition(
            id="needwood-executive-9-tenfore",
            name="Needwood Golf Course - Executive 9",
            provider="tenfore",
            timezone="America/New_York",
            provider_config={
                "golf_course_id": 16509,
                "sub_course_id": 1031,
                "vanity_name": "needwood",
                "default_holes": 9,
                "prefer_holes": 9,
            },
        )
        payload = {
            "successful": True,
            "data": [
                {
                    "id": 5206390,
                    "date": "2026-03-27",
                    "time": "15:00:00",
                    "spots": 2,
                    "feeTitle": "Public",
                    "fullPrice18": 68.0,
                    "feePrice18": 68.0,
                    "fullPrice9": 24.0,
                    "feePrice9": 24.0,
                }
            ],
        }
        http_client = StubHttpClient(payload=payload)
        service = TeeTimeService([course], http_client=http_client)

        results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=2,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].price, 24.0)
        self.assertEqual(results[0].holes, 9)
        self.assertEqual(
            json.loads(http_client.requests[0]["body"]),
            {
                "golfCourseId": 16509,
                "subCourseId": 1031,
                "dateFrom": "2026-03-27",
                "appId": 71,
            },
        )

    def test_tenfore_provider_can_fall_back_to_generic_recipe_mode(self) -> None:
        course = CourseDefinition(
            id="mcg-generic",
            name="MCG Generic",
            provider="tenfore",
            provider_config={
                "endpoint": "https://example.com/api/search",
                "items_path": "results",
                "starts_at_field": "startsAt",
                "price_field": "price",
                "available_players_field": "availablePlayers",
                "booking_url_field": "bookingUrl",
            },
        )
        http_client = StubHttpClient()
        service = TeeTimeService([course], http_client=http_client)
        request = SearchRequest(
            date=date.fromisoformat("2026-03-27"),
            players=2,
        )

        results = service.search(request)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].price, 40.75)
        self.assertEqual(http_client.requests[0]["url"], "https://example.com/api/search")

    def test_teeitup_provider_queries_live_style_endpoint_and_normalizes_rates(self) -> None:
        course = CourseDefinition(
            id="pohick-bay",
            name="Pohick Bay Regional Parks Golf Course",
            provider="teeitup",
            timezone="America/New_York",
            booking_url="https://nova-parks.book.teeitup.com/?course=1172",
            provider_config={
                "alias": "nova-parks",
                "facility_id": 1172,
                "be_api_url": "https://phx-api-be-east-1b.kenna.io",
                "prefer_holes": 18,
                "booking_url_template": "https://nova-parks.book.teeitup.com/?course={facility_id}&date={date}",
            },
        )
        payload = [
            {
                "courseId": "54f14bb90c8ad60378b01532",
                "teetimes": [
                    {
                        "teetime": "2026-03-27T12:10:00.000Z",
                        "bookedPlayers": 0,
                        "minPlayers": 1,
                        "maxPlayers": 4,
                        "rates": [
                            {
                                "name": "18 Holes",
                                "holes": 18,
                                "allowedPlayers": [1, 2, 3, 4],
                                "greenFeeCart": 7300,
                            },
                            {
                                "name": "9 Holes",
                                "holes": 9,
                                "allowedPlayers": [1, 2, 3, 4],
                                "greenFeeCart": 5000,
                            },
                        ],
                    }
                ],
            }
        ]
        http_client = StubHttpClient(payload=payload)
        service = TeeTimeService([course], http_client=http_client)
        request = SearchRequest(
            date=date.fromisoformat("2026-03-27"),
            players=2,
        )

        results = service.search(request)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].starts_at.strftime("%Y-%m-%d %H:%M"), "2026-03-27 08:10")
        self.assertEqual(results[0].price, 50.0)
        self.assertEqual(results[0].price_min, 50.0)
        self.assertEqual(results[0].price_max, 73.0)
        self.assertIsNone(results[0].holes)
        self.assertEqual(results[0].hole_options, (9, 18))
        self.assertEqual(results[0].player_options, (1, 2, 3, 4))
        self.assertIsNone(results[0].rate_name)
        self.assertEqual(
            results[0].booking_url,
            "https://nova-parks.book.teeitup.com/?course=1172&date=2026-03-27",
        )
        self.assertEqual(len(http_client.requests), 1)
        recorded_request = http_client.requests[0]
        self.assertEqual(
            recorded_request["url"],
            "https://phx-api-be-east-1b.kenna.io/v2/tee-times?date=2026-03-27&facilityIds=1172",
        )
        self.assertEqual(recorded_request["headers"]["x-be-alias"], "nova-parks")

    def test_teeitup_provider_can_fall_back_to_generic_recipe_mode(self) -> None:
        course = CourseDefinition(
            id="pohick-generic",
            name="Pohick Generic",
            provider="teeitup",
            provider_config={
                "endpoint": "https://example.com/api/search",
                "items_path": "results",
                "starts_at_field": "startsAt",
                "price_field": "price",
                "available_players_field": "availablePlayers",
                "booking_url_field": "bookingUrl",
            },
        )
        http_client = StubHttpClient()
        service = TeeTimeService([course], http_client=http_client)
        request = SearchRequest(
            date=date.fromisoformat("2026-03-27"),
            players=2,
        )

        results = service.search(request)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].price, 40.75)
        self.assertEqual(http_client.requests[0]["url"], "https://example.com/api/search")

    def test_teeitup_provider_uses_allowed_players_for_availability(self) -> None:
        course = CourseDefinition(
            id="pohick-bay",
            name="Pohick Bay Regional Parks Golf Course",
            provider="teeitup",
            timezone="America/New_York",
            provider_config={
                "alias": "nova-parks",
                "facility_id": 1172,
            },
        )
        payload = [
            {
                "teetimes": [
                    {
                        "teetime": "2026-03-27T11:40:00.000Z",
                        "bookedPlayers": 2,
                        "maxPlayers": 2,
                        "rates": [
                            {
                                "name": "18 Holes",
                                "holes": 18,
                                "allowedPlayers": [1, 2],
                                "greenFeeCart": 7300,
                            }
                        ],
                    }
                ]
            }
        ]
        http_client = StubHttpClient(payload=payload)
        service = TeeTimeService([course], http_client=http_client)

        blocked_results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=2,
            )
        )
        self.assertEqual(len(blocked_results), 1)
        self.assertEqual(blocked_results[0].starts_at.strftime("%H:%M"), "07:40")
        self.assertEqual(blocked_results[0].available_players, 2)
        self.assertEqual(blocked_results[0].player_options, (1, 2))

        single_results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=1,
            )
        )
        self.assertEqual(len(single_results), 1)
        self.assertEqual(single_results[0].available_players, 2)

        four_player_results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=4,
            )
        )
        self.assertEqual(four_player_results, [])

    def test_teeitup_provider_holes_filter_selects_single_hole_option(self) -> None:
        course = CourseDefinition(
            id="pohick-bay",
            name="Pohick Bay Regional Parks Golf Course",
            provider="teeitup",
            timezone="America/New_York",
            provider_config={
                "alias": "nova-parks",
                "facility_id": 1172,
                "prefer_holes": 18,
            },
        )
        payload = [
            {
                "teetimes": [
                    {
                        "teetime": "2026-03-27T11:50:00.000Z",
                        "maxPlayers": 4,
                        "rates": [
                            {
                                "name": "18 Holes",
                                "holes": 18,
                                "allowedPlayers": [1, 2, 3, 4],
                                "greenFeeCart": 7300,
                            },
                            {
                                "name": "9 Holes",
                                "holes": 9,
                                "allowedPlayers": [1, 2, 3, 4],
                                "greenFeeCart": 5000,
                            },
                        ],
                    }
                ]
            }
        ]
        http_client = StubHttpClient(payload=payload)
        service = TeeTimeService([course], http_client=http_client)

        results = service.search(
            SearchRequest(
                date=date.fromisoformat("2026-03-27"),
                players=2,
                holes=18,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].holes, 18)
        self.assertEqual(results[0].hole_options, (18,))
        self.assertEqual(results[0].price, 73.0)
        self.assertEqual(results[0].price_min, 73.0)
        self.assertEqual(results[0].price_max, 73.0)
        self.assertEqual(results[0].rate_name, "18 Holes")


if __name__ == "__main__":
    unittest.main()
