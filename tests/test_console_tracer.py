"""Tests for ``personakit.observability.ConsoleTracer``.

The tracer is deliberately zero-dependency and renders each span as a coloured
console line. These tests capture the rendered output to an ``io.StringIO``
buffer and assert on the shape / attributes, without asserting on exact ANSI
sequences (colour is disabled in tests to keep the assertions readable).
"""

from __future__ import annotations

import io

from personakit.observability import ConsoleTracer, Tracer


def _new_tracer(**kwargs):
    buf = io.StringIO()
    tracer = ConsoleTracer(stream=buf, color=False, **kwargs)
    return tracer, buf


def test_console_tracer_satisfies_tracer_protocol():
    tracer, _ = _new_tracer()
    assert isinstance(tracer, Tracer)


def test_console_tracer_renders_analyze_span_open_and_close():
    tracer, buf = _new_tracer()
    with tracer.start_span(
        "personakit.analyze",
        specialist="code_reviewer",
        model="gpt-4o",
        provider="openai",
    ):
        pass
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "[analyze]" in lines[0]
    assert "specialist=code_reviewer" in lines[0]
    assert "model=gpt-4o" in lines[0]
    assert "[analyze] done" in lines[1]
    assert "ms" in lines[1]


def test_console_tracer_renders_provider_span_with_tokens_and_cost():
    tracer, buf = _new_tracer()
    with tracer.start_span(
        "personakit.provider.complete",
        iteration=0,
        provider="openai",
        message_count=2,
    ) as span:
        span.set_attribute("usage.prompt_tokens", 100)
        span.set_attribute("usage.completion_tokens", 40)
        span.set_attribute("model", "gpt-4o")
    output = buf.getvalue()
    assert "provider" in output
    assert "openai" in output
    assert "iter=0" in output
    assert "100→40 tok" in output
    assert "$" in output


def test_console_tracer_renders_tool_span_ok_and_err():
    tracer, buf = _new_tracer()
    with tracer.start_span("personakit.tool.invoke", tool="graph_query", known=True):
        pass
    with tracer.start_span("personakit.tool.invoke", tool="mystery", known=False) as s:
        s.set_attribute("error", "unknown_tool")
    output = buf.getvalue()
    assert "tool  graph_query" in output
    assert "ok" in output
    assert "tool  mystery" in output
    assert "err" in output


def test_console_tracer_nesting_indents_inner_spans():
    tracer, buf = _new_tracer()
    with tracer.start_span("personakit.analyze", specialist="s", model="m", provider="p"):
        with tracer.start_span("personakit.provider.complete", iteration=0, provider="p", message_count=1):
            pass
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    outer_open = lines[0]
    inner_lines = [ln for ln in lines if ln.startswith("  ")]
    assert not outer_open.startswith("  ")
    assert len(inner_lines) == 2


def test_console_tracer_live_false_only_renders_on_close():
    tracer, buf = _new_tracer(live=False)
    with tracer.start_span("personakit.analyze", specialist="s", model="m", provider="p"):
        pass
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) == 1
    assert "done" in lines[0]


def test_console_tracer_records_exceptions_on_span_close():
    tracer, buf = _new_tracer()
    try:
        with tracer.start_span("personakit.analyze", specialist="s", model="m", provider="p"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    output = buf.getvalue()
    assert "ERROR" in output
    assert "RuntimeError" in output
    assert "boom" in output


def test_console_tracer_color_autodetects_from_stream_tty():
    class _FakeTTY(io.StringIO):
        def isatty(self):
            return True

    class _FakeFile(io.StringIO):
        def isatty(self):
            return False

    tty_tracer = ConsoleTracer(stream=_FakeTTY())
    file_tracer = ConsoleTracer(stream=_FakeFile())
    assert tty_tracer._color is True
    assert file_tracer._color is False
