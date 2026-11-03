"""Gallery yt-dlp calls must not treat caller input as options.

A cover upload returns an absolute path. Passing that path as
``video_url=--config-locations=<path>`` used to be the last yt-dlp argument,
so the uploaded file could set ``--exec``. Option-style and non-http values
are rejected before spawn; an accepted URL is placed after ``--``.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import gallery


class _Finished:
    def __init__(self, returncode: int = 1):
        self.returncode = returncode

    async def communicate(self):
        return b"", b"stopped-by-test"


def _client(monkeypatch, spawned: list):
    async def capture(*args, **kwargs):
        spawned.append(args)
        return _Finished()

    monkeypatch.setattr(gallery, "spawn_subprocess", capture)
    monkeypatch.setattr(gallery, "ytdlp_invocation", lambda: (["yt-dlp"], None))
    app = FastAPI()
    app.include_router(gallery.router)
    return TestClient(app)


@pytest.mark.parametrize(
    "video_url",
    [
        "--config-locations=/tmp/evil.conf",
        "--exec=id",
        "--batch-file=/etc/passwd",
        "-o",
        "file:///etc/passwd",
        "ftp://example.com/video",
        "javascript:alert(1)",
        "/etc/passwd",
        "http://--config-locations=/tmp/evil.conf",
        "https:///no-host",
        "   ",
        "https://example.com/a\n--exec=id",
    ],
)
def test_download_rejects_option_style_and_non_http_urls(monkeypatch, video_url):
    spawned: list = []
    client = _client(monkeypatch, spawned)
    response = client.post(
        "/gallery/download",
        params={"video_url": video_url, "character_name": "clip"},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "video_url must be an http or https URL"
    assert spawned == []


@pytest.mark.parametrize(
    "video_url",
    [
        "https://example.com/watch?v=abc",
        "http://example.com/watch?v=abc",
        "HTTPS://example.com/watch?v=abc",
    ],
)
def test_download_passes_http_url_after_end_of_options(monkeypatch, video_url):
    spawned: list = []
    client = _client(monkeypatch, spawned)
    response = client.post(
        "/gallery/download",
        params={"video_url": video_url, "character_name": "clip"},
    )
    assert spawned, response.text
    argv = spawned[0]
    assert argv[0] == "yt-dlp"
    assert argv[1] == "--ignore-config"
    assert argv[-2:] == ("--", video_url.strip())
    # Spawn ran and the fake downloader failed; the URL was not a 400.
    assert response.status_code == 500


def test_search_puts_the_query_after_end_of_options(monkeypatch):
    spawned: list = []
    client = _client(monkeypatch, spawned)
    query = "--config-locations=/tmp/evil.conf"
    response = client.post(
        "/gallery/search/youtube",
        params={"query": query},
    )
    assert spawned, response.text
    argv = spawned[0]
    assert argv[1] == "--ignore-config"
    assert argv[-2:] == ("--", f"ytsearch5:{query}")
    assert response.status_code == 500
