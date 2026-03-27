from __future__ import annotations

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest, TeeTime
from tee_time_finder.providers.base import BookingProvider
from tee_time_finder.providers.html_regex import HtmlRegexProvider
from tee_time_finder.providers.json_api import JsonApiProvider


class SiteFamilyProvider(BookingProvider):
    def __init__(self) -> None:
        self.json_provider = JsonApiProvider()
        self.html_provider = HtmlRegexProvider()

    def search(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        http_client: HttpClient,
    ) -> list[TeeTime]:
        response_format = course.provider_config.get("response_format", "json").lower()
        if response_format == "json":
            return self.json_provider.search(course, request, http_client)
        if response_format == "html":
            return self.html_provider.search(course, request, http_client)
        raise ValueError(
            f"Unsupported response_format '{response_format}' for provider '{course.provider}'"
        )
