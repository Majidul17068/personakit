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


# ---- Regression: with `from __future__ import annotations` at the top of this
# module, parameter annotations are strings until resolved. Prior to v0.1.1 the
# int/float/bool/list hints all fell through to {"type": "string"}.
def test_int_float_bool_annotations_resolve():
    @tool
    def compute(
        amount: int,
        rate: float,
        flag: bool,
        tags: list[str],
        note: str,
    ) -> dict:
        """Regression fixture for stringified annotations."""
        return {}

    props = compute.to_openai_schema()["function"]["parameters"]["properties"]
    assert props["amount"]["type"] == "integer"
    assert props["rate"]["type"] == "number"
    assert props["flag"]["type"] == "boolean"
    assert props["tags"]["type"] == "array"
    assert props["tags"]["items"]["type"] == "string"
    assert props["note"]["type"] == "string"


def test_optional_annotation_marks_nullable():
    @tool
    def maybe(name: str | None = None) -> str:
        return name or ""

    props = maybe.to_openai_schema()["function"]["parameters"]["properties"]
    assert props["name"]["type"] == "string"
    assert props["name"].get("nullable") is True
