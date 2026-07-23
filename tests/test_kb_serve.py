"""Tests for scripts/kb-serve.py -- the stdlib-only HTTP facade over the
personal knowledgebase vault.

Covers the four HTTP endpoints (via a real ephemeral-port server, so the
actual do_GET/do_POST dispatch is exercised, not just the underlying pure
functions), the enrichment no-op/success/degrade paths, and the two
security-fix cases in find_unenriched_notes(). Everything runs offline:
urllib.request.urlopen / request_enrichment are mocked wherever a real
network call would otherwise happen, and every vault lives under tmp_path,
never the real ~/.knowledgebase.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "kb-serve.py"


def _load_kb_serve():
    spec = importlib.util.spec_from_file_location("kb_serve_under_test", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


kb_serve = _load_kb_serve()
KbServeConfig = kb_serve.KbServeConfig


def _config(kb_home: Path, *, enrich_enabled: bool = False, llm_api_key: str | None = None) -> KbServeConfig:
    return KbServeConfig(
        kb_home=kb_home,
        enrich_enabled=enrich_enabled,
        llm_base_url="https://example.invalid/v1",
        llm_model="fake/model",
        llm_api_key=llm_api_key,
    )


@pytest.fixture
def live_server(tmp_path: Path) -> Iterator[tuple[str, KbServeConfig]]:
    """A real kb-serve HTTP server on an ephemeral 127.0.0.1 port, backed
    by an empty vault under tmp_path."""
    config = _config(tmp_path)
    server = kb_serve.KbHTTPServer(("127.0.0.1", 0), kb_serve.KbRequestHandler, config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base_url, config
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _post(base_url: str, path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"{base_url}{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ── /health ─────────────────────────────────────────────────────────────


def test_health_reports_kb_home_indexed_count_and_ok_status(live_server: tuple[str, KbServeConfig]) -> None:
    base_url, config = live_server
    with urllib.request.urlopen(f"{base_url}/health") as response:
        assert response.status == 200
        body = json.loads(response.read())
    assert body == {"status": "ok", "kb_home": str(config.kb_home), "indexed_count": 0}


# ── /put ────────────────────────────────────────────────────────────────


def test_put_writes_note_with_expected_frontmatter(live_server: tuple[str, KbServeConfig]) -> None:
    base_url, config = live_server
    status, body = _post(base_url, "/put", {
        "project": "proj1", "title": "My Title", "content": "Body text.", "type": "note",
    })
    assert status == 201
    note_path = Path(str(body["path"]))
    assert note_path.is_relative_to(config.kb_home)
    text = note_path.read_text(encoding="utf-8")
    assert 'title: "My Title"' in text
    assert 'project: "proj1"' in text
    assert 'type: "note"' in text
    assert "Body text." in text


def test_put_missing_required_field_returns_400(live_server: tuple[str, KbServeConfig]) -> None:
    base_url, _ = live_server
    status, body = _post(base_url, "/put", {"title": "No project or content"})
    assert status == 400
    assert "project" in str(body["error"])


# ── /query ──────────────────────────────────────────────────────────────


def test_query_returns_seeded_note(live_server: tuple[str, KbServeConfig]) -> None:
    base_url, _ = live_server
    _post(base_url, "/put", {
        "project": "proj1", "title": "Distinctive Widget", "content": "widget content zzyzx",
    })
    with urllib.request.urlopen(f"{base_url}/query?q=zzyzx") as response:
        body = json.loads(response.read())
    assert len(body["results"]) == 1
    assert body["results"][0]["title"] == "Distinctive Widget"


def test_query_no_hits_returns_empty_list(live_server: tuple[str, KbServeConfig]) -> None:
    base_url, _ = live_server
    _post(base_url, "/put", {"project": "proj1", "title": "Unrelated", "content": "something else"})
    with urllib.request.urlopen(f"{base_url}/query?q=nosuchtermanywhere") as response:
        body = json.loads(response.read())
    assert body["results"] == []


# ── /enrich: KB_ENRICH=0 default -> zero network calls ────────────────────


def test_enrich_disabled_by_default_makes_zero_network_calls(tmp_path: Path) -> None:
    config = _config(tmp_path, enrich_enabled=False)
    with patch.object(kb_serve, "request_enrichment") as mock_request:
        result = kb_serve.kb_enrich(config, {})
    mock_request.assert_not_called()
    assert result == {"enriched": 0, "message": "KB_ENRICH is 0; enrichment disabled"}


# ── /enrich: KB_ENRICH=1, no resolvable key -> zero network calls ─────────


def test_enrich_enabled_without_key_makes_zero_network_calls(tmp_path: Path) -> None:
    config = _config(tmp_path, enrich_enabled=True, llm_api_key=None)
    with patch.object(kb_serve, "request_enrichment") as mock_request:
        result = kb_serve.kb_enrich(config, {})
    mock_request.assert_not_called()
    assert result["enriched"] == 0
    assert "no API key resolved" in str(result["message"])


# ── /enrich: success path -> rewrites only question/summary ───────────────


def test_enrich_success_rewrites_only_question_and_summary(tmp_path: Path) -> None:
    config = _config(tmp_path, enrich_enabled=True, llm_api_key="fake-key")
    put_result = kb_serve.kb_put(tmp_path, {
        "project": "proj1", "title": "Widget Guide", "content": "This widget does things.",
    })
    note_path = Path(str(put_result["path"]))
    text_before = note_path.read_text(encoding="utf-8")
    body_before = text_before.split("---\n", 2)[2]

    with patch.object(
        kb_serve, "request_enrichment",
        return_value={"question": "What does the widget do?", "summary": "The widget does things well."},
    ) as mock_request:
        result = kb_serve.kb_enrich(config, {})

    mock_request.assert_called_once()
    assert result == {"enriched": 1, "notes": [str(note_path)]}
    text_after = note_path.read_text(encoding="utf-8")
    assert 'question: "What does the widget do?"' in text_after
    assert 'summary: "The widget does things well."' in text_after
    assert 'title: "Widget Guide"' in text_after  # untouched
    assert text_after.split("---\n", 2)[2] == body_before  # body byte-for-byte untouched


# ── security fix: find_unenriched_notes path-escape guard ─────────────────


def test_find_unenriched_notes_rejects_absolute_path_escape(tmp_path: Path) -> None:
    result = kb_serve.find_unenriched_notes(tmp_path, None, "/etc/passwd")
    assert result == []


def test_find_unenriched_notes_rejects_dotdot_relative_escape(tmp_path: Path) -> None:
    kb_home = tmp_path / "vault"
    kb_home.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("secret note content", encoding="utf-8")
    result = kb_serve.find_unenriched_notes(kb_home, None, "../outside.md")
    assert result == []


def test_find_unenriched_notes_happy_path_returns_candidate(tmp_path: Path) -> None:
    put_result = kb_serve.kb_put(tmp_path, {
        "project": "proj1", "title": "Real Note", "content": "content",
    })
    note_path = Path(str(put_result["path"]))
    rel = note_path.relative_to(tmp_path)
    result = kb_serve.find_unenriched_notes(tmp_path, None, str(rel))
    assert result == [note_path.resolve()]


# ── security fix: kb_enrich degrades cleanly on an unreadable note ────────


def test_kb_enrich_degrades_cleanly_when_note_read_fails(tmp_path: Path) -> None:
    """A note that find_unenriched_notes listed but that vanishes/errors
    before read_text() runs must be a clean skip, never an uncaught
    exception, and the return shape stays the normal one."""
    config = _config(tmp_path, enrich_enabled=True, llm_api_key="fake-key")
    vanished_note = tmp_path / "vanished.md"  # never created on disk
    with (
        patch.object(kb_serve, "find_unenriched_notes", return_value=[vanished_note]),
        patch.object(kb_serve, "request_enrichment") as mock_request,
    ):
        result = kb_serve.kb_enrich(config, {})  # must not raise
    mock_request.assert_not_called()  # read_text raised before the network call
    assert result == {"enriched": 0, "notes": []}


# ── secret handling: resolved key never logged on command failure ─────────


def test_resolve_api_key_never_logs_secret_on_command_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    """KB_LLM_API_KEY_CMD's own stdout may contain secret-looking text
    even when it fails; that text must never reach the log."""
    secret = "sk-super-secret-fake-12345"
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text(secret, encoding="utf-8")
    # The command text itself carries no secret substring -- only its
    # stdout does, once run -- so this proves the *output*, not just the
    # invocation string, never leaks.
    cmd = f"cat {secret_file}; exit 1"

    with caplog.at_level(logging.WARNING, logger="kb-serve"):
        result = kb_serve.resolve_api_key({"KB_LLM_API_KEY_CMD": cmd})

    assert result is None
    assert secret not in caplog.text
    assert "KB_LLM_API_KEY_CMD failed" in caplog.text  # sanity: the warning path was actually hit


# ── /clip ───────────────────────────────────────────────────────────────

_CANNED_HTML = b"""<html>
<head>
<title>Fallback Title</title>
<meta property="og:title" content="Canned OG Title">
<meta property="og:description" content="A canned description of the article.">
<meta property="og:site_name" content="Example Site">
</head>
<body>
<article>
<h1>Canned OG Title</h1>
<p>This is the first canned paragraph with enough text for readability to
consider it the main content block, repeated so it is clearly the densest
node on the page for extraction purposes and passes the minimum content
length heuristics used by the readability library during scoring.</p>
<p>A second paragraph adds more length so the extractor confidently
selects this article body over any boilerplate navigation text that might
otherwise be present on a real page in the wild.</p>
</article>
</body>
</html>"""


class _FakeResponse:
    """Stand-in for what urllib.request.urlopen()'s context manager
    yields -- just enough surface (.read(), .headers.get_content_charset())
    for kb_clip.fetch_html()."""

    def __init__(self, html: bytes) -> None:
        self._html = html
        self.headers = SimpleNamespace(get_content_charset=lambda: "utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def read(self) -> bytes:
        return self._html


def _urlopen_local_passthrough_else(
    real_urlopen: Callable[..., object], *, html: bytes = b"", exc: Exception | None = None,
) -> Callable[..., object]:
    """Build a urllib.request.urlopen side_effect: calls to the
    live_server's own 127.0.0.1 port pass through to the real urlopen (so
    _post() keeps talking to the test server); any other URL -- the
    "external" one /clip fetches -- is intercepted and never hits the
    network: returns canned `html`, or raises `exc` if given."""

    def _side_effect(request: urllib.request.Request, *args: object, **kwargs: object) -> object:
        if "127.0.0.1" in request.full_url:
            return real_urlopen(request, *args, **kwargs)
        if exc is not None:
            raise exc
        return _FakeResponse(html)

    return _side_effect


def test_clip_happy_path_writes_source_note_with_extracted_content(
    live_server: tuple[str, KbServeConfig],
) -> None:
    base_url, config = live_server
    real_urlopen = urllib.request.urlopen
    with patch(
        "urllib.request.urlopen", side_effect=_urlopen_local_passthrough_else(real_urlopen, html=_CANNED_HTML),
    ) as mock_urlopen:
        status, body = _post(base_url, "/clip", {"url": "https://example.invalid/article", "project": "proj1"})

    assert status == 201
    external_calls = [c for c in mock_urlopen.call_args_list if "example.invalid" in c.args[0].full_url]
    assert len(external_calls) == 1  # the outbound fetch went through the mock, never the real network

    note_path = Path(str(body["path"]))
    assert note_path.is_relative_to(config.kb_home)
    text = note_path.read_text(encoding="utf-8")
    assert 'type: "source"' in text
    assert 'title: "Canned OG Title"' in text
    assert 'source: "https://example.invalid/article"' in text
    assert "canned paragraph" in text
    assert set(body.keys()) == {"path", "children"}  # no unexpected/leaked fields in the response


def test_clip_fetch_failure_returns_clean_error_and_writes_no_note(tmp_path: Path) -> None:
    """A URLError from the outbound fetch must come back as a clean 502,
    never a 500 stack leak, and must leave the vault untouched. The
    config here carries a fake secret /clip never touches, to prove a
    failure path can't echo it back to the client."""
    secret = "sk-should-never-leak-6f6f6f"  # noqa: S105 test fixture value, not a real secret
    config = _config(tmp_path, llm_api_key=secret)
    server = kb_serve.KbHTTPServer(("127.0.0.1", 0), kb_serve.KbRequestHandler, config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        real_urlopen = urllib.request.urlopen
        with patch(
            "urllib.request.urlopen",
            side_effect=_urlopen_local_passthrough_else(
                real_urlopen, exc=urllib.error.URLError("name resolution failed"),
            ),
        ):
            status, body = _post(base_url, "/clip", {"url": "https://example.invalid/broken", "project": "proj1"})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 502
    assert "error" in body
    assert secret not in json.dumps(body)
    assert list(tmp_path.rglob("*.md")) == []  # no partial note written
