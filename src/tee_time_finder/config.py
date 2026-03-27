from __future__ import annotations

import json
from pathlib import Path

from tee_time_finder.models import CourseDefinition


def load_courses(config_path: str | Path) -> list[CourseDefinition]:
    path = Path(config_path)
    data = json.loads(path.read_text())
    return [
        CourseDefinition(
            id=item["id"],
            name=item["name"],
            provider=item["provider"],
            timezone=item.get("timezone", "America/New_York"),
            booking_url=item.get("booking_url"),
            provider_config=item.get("provider_config", {}),
        )
        for item in data.get("courses", [])
    ]
