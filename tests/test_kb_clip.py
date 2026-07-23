"""Tests for scripts/kb-clip.py -- URL-scheme allowlisting in fetch_html.

Verifies the H1 fix: file:// (and any non-http(s) scheme) is rejected
before urlopen is ever called, closing the local-file-read reachable via
the kb-serve /clip endpoint.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "kb-clip.py"


def _load_kb_clip():
    spec = importlib.util.spec_from_file_location("kb_clip_under_test", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


kb_clip = _load_kb_clip()


@pytest.mark.parametrize(
    "url",
    ["file:///etc/hostname", "ftp://example.invalid/file", "/etc/hostname"],
)
def test_check_url_scheme_rejects_non_http(url: str) -> None:
    with pytest.raises(ValueError, match="unsupported URL scheme"):
        kb_clip.check_url_scheme(url)


@pytest.mark.parametrize("url", ["http://example.invalid/page", "https://example.invalid/page"])
def test_check_url_scheme_allows_http_https(url: str) -> None:
    kb_clip.check_url_scheme(url)  # must not raise


def test_fetch_html_rejects_file_scheme_without_reaching_urlopen() -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        with pytest.raises(ValueError, match="unsupported URL scheme"):
            kb_clip.fetch_html("file:///etc/hostname")
    mock_urlopen.assert_not_called()
