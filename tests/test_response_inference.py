import unittest

from tee_time_finder.response_inference import infer_response_mapping


class ResponseInferenceTests(unittest.TestCase):
    def test_infers_nested_fields_from_datetime_payload(self) -> None:
        payload = {
            "data": {
                "teeTimes": [
                    {
                        "slot": {
                            "startsAt": "2026-03-27T07:10:00",
                        },
                        "pricing": {
                            "offers": [
                                {
                                    "amount": "40.75",
                                    "bookingUrl": "https://example.com/slot/1",
                                }
                            ]
                        },
                        "availability": {
                            "availablePlayers": 4,
                        },
                    }
                ]
            }
        }

        suggestion = infer_response_mapping(payload)

        self.assertEqual(suggestion.items_path, "data.teeTimes")
        self.assertEqual(suggestion.starts_at_field, "slot.startsAt")
        self.assertEqual(suggestion.price_field, "pricing.offers.0.amount")
        self.assertEqual(suggestion.available_players_field, "availability.availablePlayers")
        self.assertEqual(suggestion.booking_url_field, "pricing.offers.0.bookingUrl")

    def test_infers_separate_date_and_time_fields(self) -> None:
        payload = {
            "results": [
                {
                    "teeDate": "2026-03-27",
                    "teeTime": "07:10",
                    "rates": [
                        {
                            "amount": 40.75,
                        }
                    ],
                    "links": {
                        "book": "https://example.com/slot/1",
                    },
                    "availability": {
                        "remaining": 4,
                    },
                }
            ]
        }

        suggestion = infer_response_mapping(payload)

        self.assertEqual(suggestion.items_path, "results")
        self.assertIsNone(suggestion.starts_at_field)
        self.assertEqual(suggestion.date_field, "teeDate")
        self.assertEqual(suggestion.time_field, "teeTime")
        self.assertEqual(suggestion.price_field, "rates.0.amount")
        self.assertEqual(suggestion.available_players_field, "availability.remaining")
        self.assertEqual(suggestion.booking_url_field, "links.book")


if __name__ == "__main__":
    unittest.main()
