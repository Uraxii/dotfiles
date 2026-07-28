"""Tests for comfyui.py -- pure logic only, no live server, no network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SKILL_DIR = Path(__file__).parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

from comfyui import apply_set, classify_history_entry, extract_image_refs


def test_apply_set_injects_nested_and_coerces() -> None:
    """Dotted path walks into nested dicts; int/float parse, else stay str."""
    graph = {
        "6": {"inputs": {"text": "placeholder"}},
        "3": {"inputs": {"seed": 0, "cfg": 7}},
    }
    apply_set(graph, "6.inputs.text", "a red fox")
    apply_set(graph, "3.inputs.seed", "12345")
    apply_set(graph, "3.inputs.cfg", "7.5")

    assert graph["6"]["inputs"]["text"] == "a red fox"
    assert graph["3"]["inputs"]["seed"] == 12345
    assert isinstance(graph["3"]["inputs"]["seed"], int)
    assert graph["3"]["inputs"]["cfg"] == 7.5
    assert isinstance(graph["3"]["inputs"]["cfg"], float)


def test_apply_set_bad_path_errors_clearly() -> None:
    """A node id or field that does not exist in the template raises."""
    graph = {"6": {"inputs": {"text": "placeholder"}}}

    with pytest.raises(ValueError, match="99"):
        apply_set(graph, "99.inputs.text", "x")

    with pytest.raises(ValueError, match="not found"):
        apply_set(graph, "6.nonexistent.text", "x")


def test_extract_image_refs_parses_history() -> None:
    """A completed history entry yields one ImageRef per produced image."""
    entry = {
        "outputs": {
            "9": {
                "images": [
                    {"filename": "a.png", "subfolder": "", "type": "output"},
                    {"filename": "b.png", "subfolder": "sub", "type": "output"},
                ]
            }
        },
        "status": {"completed": True},
    }
    refs = extract_image_refs(entry)
    assert [r.filename for r in refs] == ["a.png", "b.png"]
    assert refs[1].subfolder == "sub"


def test_classify_history_entry_cache_hit_is_not_done() -> None:
    """Completed + empty outputs is the silent cache hit: 'cached', never
    'done'. This is the gotcha the spike's run.sh guarded against."""
    cached_entry = {"outputs": {}, "status": {"completed": True}}
    pending_entry = {"outputs": {}, "status": {"completed": False}}
    done_entry = {
        "outputs": {"9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}},
        "status": {"completed": True},
    }

    assert classify_history_entry(cached_entry) == "cached"
    assert classify_history_entry(pending_entry) == "pending"
    assert classify_history_entry(done_entry) == "done"
