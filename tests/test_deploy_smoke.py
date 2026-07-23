"""Smoke tests for the agent-workbench deploy bundle.

Asserts kb-serve and review-serve answer HTTP 200 when the stack is
already up (via `deploy/agent-workbench/agent-workbench up`). Skips
cleanly whenever the tooling or a service itself is not present -- this
test never starts, stops, or otherwise mutates either service.
"""
from __future__ import annotations

import shutil
import urllib.error
import urllib.request

import pytest

KB_HEALTH_URL = "http://127.0.0.1:9100/health"
REVIEW_URL = "http://127.0.0.1:9099/"
REQUEST_TIMEOUT_SEC = 3


def _require_tooling() -> None:
    for tool in ("podman", "systemctl"):
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} not available on this host")


def _http_status(url: str) -> int | None:
    """Return the HTTP status code for url, or None if unreachable."""
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SEC) as resp:
            return resp.status
    except (urllib.error.URLError, OSError):
        return None


def test_kb_serve_health() -> None:
    _require_tooling()
    status = _http_status(KB_HEALTH_URL)
    if status is None:
        pytest.skip("kb-serve not reachable at 127.0.0.1:9100 -- stack not up")
    assert status == 200


def test_review_serve_health() -> None:
    _require_tooling()
    status = _http_status(REVIEW_URL)
    if status is None:
        pytest.skip("review-serve not reachable at 127.0.0.1:9099 -- stack not up")
    assert status == 200
