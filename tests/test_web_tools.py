"""Tests for personakit.web — fetch_url, tavily_search, serper_search.

Tests use httpx's MockTransport to intercept HTTP calls so no real network
traffic is generated. We patch `httpx.get` / `httpx.post` at the module
level via monkeypatch.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from personakit.errors import ToolError

# ---------------------------------------------------------------------------
# fetch_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_url_extracts_title_and_text(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("bs4")
    from personakit.web import fetch_url

    html = """
    <html>
      <head><title>  Example Doc  </title></head>
      <body>
        <header>nav stuff</header>
        <main>
          <h1>Hello</h1>
          <p>This is the body text we want.</p>
        </main>
        <script>tracking()</script>
        <footer>copyright</footer>
      </body>
    </html>
    """

    def mock_get(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            200,
            text=html,
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", mock_get)

    result = await fetch_url.invoke(url="https://example.com/doc")
    assert result["title"] == "Example Doc"
    assert "This is the body text we want." in result["text"]
    assert "tracking" not in result["text"]      # script stripped
    assert "nav stuff" not in result["text"]      # header stripped
    assert "copyright" not in result["text"]      # footer stripped
    assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_fetch_url_truncates_to_max_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("bs4")
    from personakit.web import fetch_url

    html = "<html><body>" + ("ABCDE " * 10000) + "</body></html>"

    def mock_get(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", mock_get)

    result = await fetch_url.invoke(url="https://example.com/big", max_chars=200)
    # +1 for the trailing ellipsis we add when truncating
    assert len(result["text"]) <= 201
    assert result["text"].endswith("…")


@pytest.mark.asyncio
async def test_fetch_url_returns_error_dict_on_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("bs4")
    from personakit.web import fetch_url

    def mock_get(url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("name resolution failed", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", mock_get)

    result = await fetch_url.invoke(url="https://does-not-exist.example")
    assert "error" in result
    assert "ConnectError" in result["error"]
    assert result["url"] == "https://does-not-exist.example"


def test_fetch_url_has_correct_tool_schema() -> None:
    pytest.importorskip("bs4")
    from personakit.web import fetch_url

    schema = fetch_url.to_openai_schema()
    assert schema["function"]["name"] == "fetch_url"
    params = schema["function"]["parameters"]["properties"]
    assert params["url"]["type"] == "string"
    assert params["max_chars"]["type"] == "integer"


# ---------------------------------------------------------------------------
# tavily_search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tavily_search_calls_correct_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from personakit.web import tavily_search

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-key")

    captured: dict[str, Any] = {}

    def mock_post(url: str, **kwargs: Any) -> httpx.Response:
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Result 1",
                        "url": "https://example.com/1",
                        "content": "Snippet for result 1.",
                        "score": 0.9,
                    },
                    {
                        "title": "Result 2",
                        "url": "https://example.com/2",
                        "content": "Snippet for result 2.",
                        "score": 0.8,
                    },
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", mock_post)

    results = await tavily_search.invoke(query="test query", max_results=2)
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["json"]["api_key"] == "tvly-test-key"
    assert captured["json"]["query"] == "test query"
    assert captured["json"]["max_results"] == 2
    assert len(results) == 2
    assert results[0]["title"] == "Result 1"


@pytest.mark.asyncio
async def test_tavily_search_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from personakit.web import tavily_search

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(ToolError) as exc_info:
        await tavily_search.invoke(query="x")
    assert "TAVILY_API_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tavily_search_clamps_max_results(monkeypatch: pytest.MonkeyPatch) -> None:
    from personakit.web import tavily_search

    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    captured: dict[str, Any] = {}

    def mock_post(url: str, **kwargs: Any) -> httpx.Response:
        captured["json"] = kwargs.get("json")
        return httpx.Response(200, json={"results": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", mock_post)

    await tavily_search.invoke(query="x", max_results=999)
    assert captured["json"]["max_results"] == 10  # clamped to 10


# ---------------------------------------------------------------------------
# serper_search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_serper_search_calls_correct_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from personakit.web import serper_search

    monkeypatch.setenv("SERPER_API_KEY", "serp-test-key")

    captured: dict[str, Any] = {}

    def mock_post(url: str, **kwargs: Any) -> httpx.Response:
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        captured["json"] = kwargs.get("json")
        return httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "title": "Title A",
                        "link": "https://example.com/a",
                        "snippet": "snippet a",
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", mock_post)

    results = await serper_search.invoke(query="hello world", max_results=1)
    assert captured["url"] == "https://google.serper.dev/search"
    assert captured["headers"]["X-API-KEY"] == "serp-test-key"
    assert captured["json"]["q"] == "hello world"
    assert captured["json"]["num"] == 1
    assert len(results) == 1
    assert results[0]["title"] == "Title A"


@pytest.mark.asyncio
async def test_serper_search_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from personakit.web import serper_search

    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    with pytest.raises(ToolError) as exc_info:
        await serper_search.invoke(query="x")
    assert "SERPER_API_KEY" in str(exc_info.value)


# ---------------------------------------------------------------------------
# All web tools should be discoverable as a single import
# ---------------------------------------------------------------------------

def test_all_web_tools_exported() -> None:
    from personakit.web import (
        extract_article,
        fetch_url,
        serper_search,
        tavily_search,
    )

    for t in (fetch_url, extract_article, serper_search, tavily_search):
        assert hasattr(t, "to_openai_schema")
        assert hasattr(t, "invoke")
