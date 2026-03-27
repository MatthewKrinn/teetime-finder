import tempfile
import unittest
from pathlib import Path

from tee_time_finder.config import load_courses


class ConfigTests(unittest.TestCase):
    def test_load_courses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "courses.json"
            config_path.write_text(
                """
                {
                  "courses": [
                    {
                      "id": "falls-road",
                      "name": "Falls Road Golf Course",
                      "provider": "tenfore",
                      "group": "MCG",
                      "provider_config": {
                        "golf_course_id": 16503
                      }
                    }
                  ]
                }
                """
            )

            courses = load_courses(config_path)
            self.assertEqual(len(courses), 1)
            self.assertEqual(courses[0].id, "falls-road")
            self.assertEqual(courses[0].group, "MCG")


if __name__ == "__main__":
    unittest.main()
