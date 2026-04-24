"""Opt-in tool integration.

personakit's core has zero coupling to tool-calling. When a user wants tools —
for example, to integrate external memory, a database lookup, or an API call —
they decorate a function with `@tool` and pass it to `Agent.with_tools(...)`.

The `@tool` decorator builds an OpenAI-compatible JSON schema from the
function's signature and docstring. Agents forward the schema to providers that
support tool calling (OpenAI, Anthropic). Providers that don't support tools
ignore the payload.
"""

from __future__ import annotations

import asyncio
import inspect
import types
import typing
from collections.abc import Callable
from typing import Any, Union, get_args, get_origin

from .errors import ToolError

# PEP 604 `X | Y` produces `types.UnionType`; typing.Union[X, Y] produces a
# different origin. Treat both as unions for JSON-schema purposes.
_UNION_TYPES: tuple[Any, ...] = (Union, types.UnionType)


def _resolve_hints(func: Callable[..., Any]) -> dict[str, Any]:
    """Return a name -> resolved-annotation map for `func`.

    Callers often decorate tool functions in modules that use
    `from __future__ import annotations`, which stringifies annotations at
    module load. `inspect.Parameter.annotation` then yields the raw string
    (e.g. "int") rather than the actual type object — so we evaluate via
    `typing.get_type_hints`, which resolves those strings against the
    function's globals/locals.
    """
    try:
        return typing.get_type_hints(func, include_extras=True)
    except (NameError, TypeError, AttributeError):
        return {}


class Tool:
    """Runtime-callable wrapper around a user-registered function.

    Instances expose `.to_openai_schema()` so the Agent can forward them to
    providers that speak the OpenAI tool-calling dialect. They also expose
    `.invoke(**kwargs)` for async execution.
    """

    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        self.func = func
        self.name = name or func.__name__
        self.description = description or (inspect.getdoc(func) or "").strip()
        self._signature = inspect.signature(func)
        self._schema = _build_schema(func, self._signature, self.description)

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._schema,
            },
        }

    async def invoke(self, **kwargs: Any) -> Any:
        try:
            result = self.func(**kwargs)
        except TypeError as exc:
            raise ToolError(f"Tool {self.name!r} invocation failed: {exc}") from exc
        if inspect.isawaitable(result):
            return await result
        return result


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Tool | Callable[[Callable[..., Any]], Tool]:
    """Decorator — register a function as a personakit tool.

    Usage:

        @tool
        def lookup_patient(patient_id: str) -> dict:
            '''Fetch a patient record by id.'''
            ...

        @tool(name="search_kb", description="Search the knowledge base.")
        async def search(query: str, top_k: int = 5) -> list[str]:
            ...
    """
    if func is not None and callable(func):
        return Tool(func, name=name, description=description)

    def _wrap(f: Callable[..., Any]) -> Tool:
        return Tool(f, name=name, description=description)

    return _wrap


class ToolBox:
    """A small named collection of Tools for convenient bundling."""

    def __init__(self, *tools: Tool) -> None:
        self._tools: dict[str, Tool] = {}
        for t in tools:
            self.add(t)

    def add(self, tool_obj: Tool) -> None:
        if tool_obj.name in self._tools:
            raise ToolError(f"Tool {tool_obj.name!r} already in the toolbox.")
        self._tools[tool_obj.name] = tool_obj

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolError(f"No tool named {name!r}.") from exc

    def as_list(self) -> list[Tool]:
        return list(self._tools.values())


def _build_schema(
    func: Callable[..., Any],
    sig: inspect.Signature,
    description: str,
) -> dict[str, Any]:
    hints = _resolve_hints(func)
    props: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        if param_name in {"self", "cls"}:
            continue
        annotation = hints.get(param_name, param.annotation)
        json_type = _annotation_to_json(annotation)
        props[param_name] = json_type
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": props,
    }
    if required:
        schema["required"] = required
    if description:
        schema["description"] = description
    return schema


def _annotation_to_json(annotation: Any) -> dict[str, Any]:
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {"type": "string"}
    origin = get_origin(annotation)
    if origin in _UNION_TYPES:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            inner = _annotation_to_json(args[0])
            inner["nullable"] = True
            return inner
        return {"type": "string"}
    if origin is list or annotation is list:
        args = list(get_args(annotation))
        item = _annotation_to_json(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item}
    if origin is dict or annotation is dict:
        return {"type": "object"}
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }
    if annotation in mapping:
        return {"type": mapping[annotation]}
    return {"type": "string"}


def _noop() -> None:
    """Kept so that tests can import without running side effects."""
    asyncio.get_event_loop  # noqa: B018 - reference, not a call
