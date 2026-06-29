from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.sources import get_source_validation_service


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str]
    text: str
    url: str


class FakeRepo:
    def __init__(self):
        self.upsert_source = AsyncMock(return_value={"id": 11})
        self.insert_validation_run = AsyncMock(return_value={"id": 22})
        self.insert_fetch_run = AsyncMock(return_value={"id": 33})


class FakeFetcher:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.calls: list[str] = []

    async def get(self, url: str) -> FakeResponse:
        self.calls.append(url)
        return self.responses[url]


def build_service(responses: dict[str, FakeResponse]):
    from services.source_validation import SourceValidationService

    return SourceValidationService(repo=FakeRepo(), fetcher=FakeFetcher(responses))


def test_validate_rss_source_is_supported_and_persisted():
    rss_url = "https://example.com/feed.xml"
    service = build_service(
        {
            rss_url: FakeResponse(
                status_code=200,
                headers={"content-type": "application/rss+xml; charset=utf-8"},
                text="""<?xml version="1.0" encoding="UTF-8"?>
                <rss version="2.0">
                  <channel>
                    <title>Example Feed</title>
                    <link>https://example.com/</link>
                    <description>Example feed</description>
                    <item>
                      <title>Hello RSS</title>
                      <link>https://example.com/posts/1</link>
                    </item>
                  </channel>
                </rss>""",
                url=rss_url,
            )
        }
    )
    app.dependency_overrides[get_source_validation_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post("/sources/validate", json={"url": rss_url})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "source_validation"
    assert payload["duration_ms"] >= 0
    assert payload["errors"] == []
    assert payload["data"]["classification"] == "supported"
    assert payload["data"]["parser_strategy"] == "rss"
    assert payload["data"]["trust_level"] == "trusted"
    assert payload["data"]["source_id"] == 11
    assert payload["data"]["validation_run_id"] == 22


def test_fetch_html_source_is_supported():
    html_url = "https://example.com/article"
    service = build_service(
        {
            html_url: FakeResponse(
                status_code=200,
                headers={"content-type": "text/html; charset=utf-8"},
                text="""
                <html>
                  <head><title>Example Article</title></head>
                  <body>
                    <article>
                      <h1>Example Article</h1>
                      <p>This is a simple article body.</p>
                    </article>
                  </body>
                </html>
                """,
                url=html_url,
            )
        }
    )
    app.dependency_overrides[get_source_validation_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post("/sources/fetch", json={"url": html_url})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "source_validation"
    assert payload["data"]["classification"] == "supported"
    assert payload["data"]["parser_strategy"] == "html"
    assert payload["data"]["trust_level"] == "mixed"
    assert payload["data"]["items_seen"] == 1
    assert payload["data"]["fetch_run_id"] == 33


@pytest.mark.parametrize(
    "url,expected_classification",
    [
        ("https://www.youtube.com/watch?v=abc123", "blocked"),
        ("https://example.com/file.pdf", "blocked"),
        ("https://bit.ly/abc123", "suspicious"),
    ],
)
def test_unsupported_and_suspicious_urls_are_flagged(url: str, expected_classification: str):
    service = build_service({url: FakeResponse(status_code=200, headers={"content-type": "text/html"}, text="", url=url)})
    app.dependency_overrides[get_source_validation_service] = lambda: service
    client = TestClient(app)

    try:
        response = client.post("/sources/validate", json={"url": url})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["classification"] == expected_classification
    assert payload["data"]["parser_strategy"] in {"blocked", "html"}
    if expected_classification == "blocked":
        assert payload["data"]["parser_strategy"] == "blocked"


def test_persistence_path_records_source_metadata():
    from services.source_validation import SourceValidationService

    rss_url = "https://example.com/feed"
    fetcher = FakeFetcher(
        {
            rss_url: FakeResponse(
                status_code=200,
                headers={"content-type": "application/rss+xml"},
                text="""<?xml version="1.0"?><rss><channel><title>Feed</title></channel></rss>""",
                url=rss_url,
            )
        }
    )
    repo = FakeRepo()
    service = SourceValidationService(repo=repo, fetcher=fetcher)

    result = asyncio.run(service.validate_source(rss_url))

    assert result["classification"] == "supported"
    assert result["parser_strategy"] == "rss"
    assert result["source_id"] == 11
    assert result["validation_run_id"] == 22
    assert repo.upsert_source.await_count == 1
    assert repo.insert_validation_run.await_count == 1
    assert fetcher.calls == [rss_url]
