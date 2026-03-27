from __future__ import annotations

import json
from urllib.request import Request, urlopen


class HttpClient:
    def request_text(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | bytes | None = None,
    ) -> str:
        data = body.encode("utf-8") if isinstance(body, str) else body
        request = Request(url, data=data, headers=headers or {}, method=method.upper())
        with urlopen(request) as response:
            return response.read().decode("utf-8")

    def request_json(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | bytes | None = None,
    ) -> object:
        return json.loads(self.request_text(url, method=method, headers=headers, body=body))

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        return self.request_text(url, headers=headers)

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> object:
        return self.request_json(url, headers=headers)
