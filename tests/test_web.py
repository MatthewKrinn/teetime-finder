import unittest

from tee_time_finder.models import CourseDefinition
from tee_time_finder.web import _read_static_text, infer_course_group, parse_request, serialize_courses


class WebTests(unittest.TestCase):
    def test_parse_request_supports_holes_and_course_ids(self) -> None:
        request = parse_request(
            {
                "date": ["2026-03-27"],
                "players": ["2"],
                "earliest": ["12:00"],
                "latest": ["16:00"],
                "holes": ["18"],
                "course_id": ["falls-road-tenfore", "pohick-bay-teeitup"],
            }
        )

        self.assertEqual(request.holes, 18)
        self.assertEqual(request.course_ids, {"falls-road-tenfore", "pohick-bay-teeitup"})

    def test_serialize_courses_exposes_group_metadata(self) -> None:
        courses = [
            CourseDefinition(
                id="falls-road-tenfore",
                name="Falls Road Golf Course",
                provider="tenfore",
            ),
            CourseDefinition(
                id="pohick-bay-teeitup",
                name="Pohick Bay Regional Golf Course (TeeItUp)",
                provider="teeitup",
                provider_config={"alias": "nova-parks"},
            ),
            CourseDefinition(
                id="custom-course",
                name="Custom Course",
                provider="json_api",
                group="Weekend League",
            ),
        ]

        payload = serialize_courses(courses)

        self.assertEqual(payload[0]["group"], "MCG")
        self.assertEqual(payload[1]["group"], "Pohick")
        self.assertEqual(payload[2]["group"], "Weekend League")

    def test_infer_course_group_handles_fairfax_alias(self) -> None:
        course = CourseDefinition(
            id="laurel-hill-teeitup",
            name="Laurel Hill Golf Club",
            provider="teeitup",
            provider_config={"alias": "fairfax-county-mco"},
        )

        self.assertEqual(infer_course_group(course), "Fairfax")

    def test_static_ui_shell_exists(self) -> None:
        html = _read_static_text("index.html")

        self.assertIn("Search Live Tee Times", html)
        self.assertIn("/assets/app.js", html)


if __name__ == "__main__":
    unittest.main()
