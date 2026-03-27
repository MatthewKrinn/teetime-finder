from __future__ import annotations

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest, TeeTime
from tee_time_finder.providers import provider_registry


class TeeTimeService:
    def __init__(
        self,
        courses: list[CourseDefinition],
        http_client: HttpClient | None = None,
    ) -> None:
        self.courses = courses
        self.http_client = http_client or HttpClient()

    def list_courses(self) -> list[CourseDefinition]:
        return list(self.courses)

    def search(self, request: SearchRequest) -> list[TeeTime]:
        results: list[TeeTime] = []
        for course in self.courses:
            if request.course_ids and course.id not in request.course_ids:
                continue
            provider = provider_registry.get(course.provider)
            if provider is None:
                continue
            results.extend(provider.search(course, request, self.http_client))
        return sorted(results, key=lambda item: (item.starts_at, item.course_name))
