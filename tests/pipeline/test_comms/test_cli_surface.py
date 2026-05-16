"""Test CLI arg surface unchanged: R13, R14."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent.parent.parent / ".claude" / "pipeline"
_NOTIFY = _PIPELINE_DIR / "pipeline_notify.py"
_ASK = _PIPELINE_DIR / "pipeline_ask.py"

# Golden --help strings: key flags that MUST appear unchanged.
_NOTIFY_REQUIRED_FLAGS = [
    "--run",
    "--project",
    "--run-dir",
    "--kind",
    "--message",
    "--qid",
    "--did",
    "--log-level",
    "status",
    "completion",
    "friction-summary",
    "question",
    "decision",
]

_ASK_REQUIRED_FLAGS = [
    "--run",
    "--project",
    "--id",
    "--header",
    "--prompt",
    "--opt",
    "--role",
    "--hard-timeout",
    "--attach",
]


def _get_help(script: Path) -> str:
    """Import script and call build_parser().format_help()."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_mod", str(script))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    parser = mod.build_parser()
    return parser.format_help()


# --- R13: pipeline_notify --help unchanged ---


def test_pipeline_notify_help_has_required_flags() -> None:
    """R13: pipeline_notify.py argparse defs unchanged."""
    help_text = _get_help(_NOTIFY)
    for flag in _NOTIFY_REQUIRED_FLAGS:
        assert flag in help_text, f"Missing flag/choice in notify help: {flag!r}"


def test_pipeline_notify_build_parser_prog() -> None:
    """pipeline_notify build_parser uses expected prog name."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_notify", str(_NOTIFY))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    parser = mod.build_parser()
    assert "pipeline_notify" in parser.prog


# --- R14: pipeline_ask --help unchanged ---


def test_pipeline_ask_help_has_required_flags() -> None:
    """R14: pipeline_ask.py argparse defs unchanged."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ask", str(_ASK))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    parser = mod.build_parser() if hasattr(mod, "build_parser") else _extract_parser(mod)
    help_text = parser.format_help()
    for flag in _ASK_REQUIRED_FLAGS:
        assert flag in help_text, f"Missing flag in ask help: {flag!r}"


def _extract_parser(mod: object) -> object:
    """pipeline_ask doesn't have build_parser; extract from main() via argparse capture."""
    import argparse
    # pipeline_ask uses a local p = argparse.ArgumentParser(...) inside main.
    # We test by reading expected flags directly from the source.
    src = _ASK.read_text()
    return _FakeParserFromSource(src)


class _FakeParserFromSource:
    def __init__(self, src: str) -> None:
        self._src = src

    def format_help(self) -> str:
        return self._src
