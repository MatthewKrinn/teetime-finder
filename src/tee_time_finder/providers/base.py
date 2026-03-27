from __future__ import annotations

from abc import ABC, abstractmethod

from tee_time_finder.http_client import HttpClient
from tee_time_finder.models import CourseDefinition, SearchRequest, TeeTime


class BookingProvider(ABC):
    @abstractmethod
    def search(
        self,
        course: CourseDefinition,
        request: SearchRequest,
        http_client: HttpClient,
    ) -> list[TeeTime]:
        raise NotImplementedError
