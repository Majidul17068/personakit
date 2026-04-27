"""Web-knowledge tools — opt-in via the `personakit[web]` extra.

These tools let a `Specialist` use any URL as an external knowledge source.
Two patterns are supported:

1. **Pre-fetch the link** before calling the agent and pass the content as
   `extra_context=` to `Agent.analyze()` — deterministic, single LLM call,
   no tool loop needed.

2. **Let the LLM decide** when to fetch — attach these as tools via
   `Agent.with_tools([fetch_url, tavily_search])`. The Agent's tool loop
   invokes them when the LLM emits a `tool_call`.

All tools work cross-provider — OpenAI, Anthropic, LiteLLM, and any
OpenAI-compatible endpoint — because personakit's tool-loop normalises
between provider formats internally.

Install:
    pip install 'personakit[web]'

Usage:
    from personakit import Agent
    from personakit.web import fetch_url, tavily_search
    from personakit.examples import FINTECH_TRANSACTION_REVIEWER

    # Pattern 1: prefetch
    fetched = await fetch_url.invoke(url="https://example.com/doc")
    result = await agent.analyze(question, extra_context=fetched["text"])

    # Pattern 2: LLM decides
    agent = (
        Agent(specialist=FINTECH_TRANSACTION_REVIEWER, model="gpt-4o-mini")
        .with_tools([fetch_url, tavily_search])
    )
    result = await agent.analyze("Verify the entity at https://...")
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from .errors import MissingDependencyError, ToolError
from .tools import tool


def _fetch_url_impl(url: str, max_chars: int = 8000) -> dict[str, Any]:
    """Underlying implementation of fetch_url — separate from the @tool wrapper
    so other tools (extract_article fallback) can call it directly."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise MissingDependencyError(
            "fetch_url requires the 'beautifulsoup4' package. "
            "Install with: pip install 'personakit[web]'"
        ) from exc

    try:
        response = httpx.get(
            url,
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; personakit/0.1; "
                    "+https://github.com/Majidul17068/personakit)"
                )
            },
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "url": url}

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    text = " ".join(soup.get_text().split())
    if len(text) > max_chars:
        text = text[:max_chars] + "…"

    return {
        "title": title,
        "text": text,
        "status_code": response.status_code,
        "final_url": str(response.url),
    }


@tool
def fetch_url(url: str, max_chars: int = 8000) -> dict[str, Any]:
    """Fetch a URL and return its main text content with title and final URL.

    Strips scripts, styles, navigation, headers, and footers. Truncates the
    body text to `max_chars` characters to keep token usage bounded.

    Args:
        url: A fully qualified HTTP(S) URL to fetch.
        max_chars: Maximum characters of body text to return (default 8000).

    Returns:
        Dict with keys: title, text, status_code, final_url. On HTTP error,
        returns {"error": str, "url": url}.
    """
    return _fetch_url_impl(url=url, max_chars=max_chars)


@tool
def extract_article(url: str, max_chars: int = 12000) -> dict[str, Any]:
    """Extract the main article content from a URL using trafilatura.

    Better than `fetch_url` for news / blog posts / long-form articles —
    trafilatura's extractor strips boilerplate, ads, and navigation more
    aggressively than basic HTML parsing. Falls back to `fetch_url` if
    trafilatura is not installed.

    Args:
        url: A fully qualified HTTP(S) URL.
        max_chars: Maximum characters to return (default 12000).

    Returns:
        Dict with keys: title, text, author, date, url, source.
    """
    try:
        import trafilatura
    except ImportError:
        # Graceful fallback — basic fetch still works
        return _fetch_url_impl(url=url, max_chars=max_chars)

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"error": "Could not fetch URL", "url": url}
        result = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            with_metadata=True,
            output_format="json",
        )
        if not result:
            return {"error": "Could not extract article content", "url": url}
        import json as _json

        data = _json.loads(result)
        text = data.get("text", "") or ""
        if len(text) > max_chars:
            text = text[:max_chars] + "…"
        return {
            "title": data.get("title", ""),
            "text": text,
            "author": data.get("author", ""),
            "date": data.get("date", ""),
            "url": data.get("url", url),
            "source": data.get("hostname", ""),
        }
    except Exception as exc:
        raise ToolError(f"extract_article failed for {url}: {exc}") from exc


@tool
def tavily_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search the web via the Tavily API and return top results.

    Tavily is an LLM-optimised search API that includes content snippets and
    optionally a synthesised answer. Free tier offers 1,000 searches/month.
    Sign up at https://tavily.com to get an API key.

    Args:
        query: The search query.
        max_results: Number of results to return (1-10, default 5).

    Returns:
        List of dicts, each with keys: title, url, content, score.

    Raises:
        ToolError: if TAVILY_API_KEY environment variable is unset, or the
            API call fails.
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ToolError(
            "tavily_search requires the TAVILY_API_KEY environment variable. "
            "Get a free key at https://tavily.com."
        )

    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max(1, min(int(max_results), 10)),
                "search_depth": "basic",
                "include_answer": False,
            },
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ToolError(f"tavily_search HTTP error: {exc}") from exc

    data = response.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        }
        for r in data.get("results", [])
    ]


@tool
def serper_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search Google via the Serper API and return top results.

    Serper offers a generous free tier (2,500 searches) and exposes Google's
    SERP including knowledge cards, sitelinks, and answer boxes. Sign up at
    https://serper.dev to get an API key.

    Args:
        query: The search query.
        max_results: Number of results to return (1-10, default 5).

    Returns:
        List of dicts, each with keys: title, link, snippet.

    Raises:
        ToolError: if SERPER_API_KEY environment variable is unset, or the
            API call fails.
    """
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise ToolError(
            "serper_search requires the SERPER_API_KEY environment variable. "
            "Get a free key at https://serper.dev."
        )

    try:
        response = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max(1, min(int(max_results), 10))},
            timeout=20.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ToolError(f"serper_search HTTP error: {exc}") from exc

    data = response.json()
    return [
        {
            "title": r.get("title", ""),
            "link": r.get("link", ""),
            "snippet": r.get("snippet", ""),
        }
        for r in data.get("organic", [])
    ]


__all__ = ["extract_article", "fetch_url", "serper_search", "tavily_search"]
