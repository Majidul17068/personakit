from __future__ import annotations

import pytest

from personakit.tools import Tool, ToolBox, tool


def test_tool_from_function():
    @tool
    def lookup(patient_id: str) -> dict:
        """Look up a patient record."""
        return {"id": patient_id}

    assert isinstance(lookup, Tool)
    schema = lookup.to_openai_schema()
    assert schema["function"]["name"] == "lookup"
    assert schema["function"]["parameters"]["properties"]["patient_id"]["type"] == "string"
    assert schema["function"]["parameters"]["required"] == ["patient_id"]


def test_tool_with_custom_name():
    @tool(name="kb_search", description="Search the KB.")
    def search(query: str, top_k: int = 5) -> list[str]:
        return [query]

    schema = search.to_openai_schema()
    assert schema["function"]["name"] == "kb_search"
    assert schema["function"]["description"] == "Search the KB."
    assert "top_k" not in schema["function"]["parameters"].get("required", [])


@pytest.mark.asyncio
async def test_tool_invoke_sync_function():
    @tool
    def add(a: int, b: int) -> int:
        return a + b

    assert await add.invoke(a=1, b=2) == 3


@pytest.mark.asyncio
async def test_tool_invoke_async_function():
    @tool
    async def fetch(url: str) -> str:
        return f"got:{url}"

    assert await fetch.invoke(url="x") == "got:x"


def test_toolbox():
    @tool
    def one(x: str) -> str:
        return x

    @tool
    def two(y: int) -> int:
        return y

    box = ToolBox(one, two)
    assert box.get("one") is one
    assert len(box.as_list()) == 2
