"""Offline tests for snyk.py."""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.parse
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_SKILL_DIR = Path(__file__).parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

import snyk


def _issue_payload() -> dict:
    return {
        "jsonapi": {"version": "1.0"},
        "data": [
            {
                "id": "issue-1",
                "type": "issue",
                "attributes": {
                    "effective_severity_level": "critical",
                    "status": "open",
                    "type": "package_vulnerability",
                    "problems": [
                        {"id": "SNYK-JS-THING-1", "type": "vulnerability"},
                        {"id": "CVE-2026-1234", "type": "vulnerability"},
                    ],
                    "risk": {
                        "score": {"value": 891},
                        "factors": [
                            {"name": "deployed", "value": True},
                            {"name": "public_facing", "value": False},
                            {"name": "loaded_package", "value": True},
                        ],
                    },
                    "coordinates": [
                        {
                            "reachability": "function",
                            "is_fixable_snyk": False,
                            "is_fixable_upstream": True,
                            "is_fixable_manually": False,
                        },
                        {
                            "reachability": "package",
                            "is_fixable_snyk": False,
                        },
                    ],
                },
                "relationships": {},
                "meta": {},
            }
        ],
        "links": {
            "self": "https://api.snyk.io/rest/orgs/o/issues",
            "next": "https://api.snyk.io/rest/orgs/o/issues?version=2026-03-25&starting_after=abc&limit=20",
        },
    }


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


def _with_urlopen(
    func: Callable[[], None], payload: dict | None = None
) -> list[str]:
    seen: list[str] = []
    old_urlopen = snyk.urllib.request.urlopen

    def fake_urlopen(request: object, timeout: int) -> _Response:
        del timeout
        seen.append(request.full_url)
        return _Response(payload or {"jsonapi": {"version": "1.0"}, "data": []})

    snyk.urllib.request.urlopen = fake_urlopen
    try:
        func()
    finally:
        snyk.urllib.request.urlopen = old_urlopen
    return seen


def _http_error(body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://example.invalid", 403, "Forbidden", {}, io.BytesIO(body)
    )


def _stderr_from_error(body: bytes) -> str:
    old_urlopen = snyk.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> _Response:
        del timeout
        raise _http_error(body)

    snyk.urllib.request.urlopen = fake_urlopen
    stderr = io.StringIO()
    try:
        with redirect_stderr(stderr):
            try:
                snyk._get("/self", {"version": snyk.API_VERSION}, "token")
            except SystemExit as err:
                assert err.code == 1
            else:
                raise AssertionError("expected SystemExit")
    finally:
        snyk.urllib.request.urlopen = old_urlopen
    return stderr.getvalue()


def test_issue_prioritization_projection() -> None:
    assert snyk._issue_rows(_issue_payload()) == [
        (
            "issue-1",
            "critical",
            "open",
            "package_vulnerability",
            "CVE-2026-1234",
            891,
            "deployed,loaded_package",
            "function,package",
            True,
        )
    ]


def test_snyk_problem_fallback() -> None:
    payload = _issue_payload()
    payload["data"][0]["attributes"]["problems"] = [{"id": "SNYK-JS-THING-1"}]
    assert snyk._issue_rows(payload)[0][4] == "SNYK-JS-THING-1"


def test_limit_clamping() -> None:
    assert snyk._clamp_limit("orgs", 1) == 10
    assert snyk._clamp_limit("issues", 500) == 100
    assert snyk._clamp_limit("targets", 0) == 10
    assert snyk._clamp_limit("targets", 20) == 20


def test_token_missing_exits() -> None:
    old_token = os.environ.pop("SNYK_TOKEN", None)
    try:
        try:
            snyk._token()
        except SystemExit as err:
            assert "SNYK_TOKEN" in str(err)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        if old_token is not None:
            os.environ["SNYK_TOKEN"] = old_token


def test_next_url_fetched_verbatim() -> None:
    old_token = os.environ.get("SNYK_TOKEN")
    os.environ["SNYK_TOKEN"] = "token-for-test"
    next_url = (
        "https://api.snyk.io/rest/orgs/o/issues?"
        "version=2026-03-25&starting_after=opaque%2Fcursor&limit=20"
    )
    try:
        seen = _with_urlopen(
            lambda: snyk.main(["issues", "--org", "o", "--next", next_url])
        )
    finally:
        if old_token is None:
            os.environ.pop("SNYK_TOKEN", None)
        else:
            os.environ["SNYK_TOKEN"] = old_token
    assert seen == [next_url]


def test_next_relative_cursor_fetched_verbatim() -> None:
    old_token = os.environ.get("SNYK_TOKEN")
    os.environ["SNYK_TOKEN"] = "token-for-test"
    relative_next = (
        "/orgs/o/issues?version=2026-03-25&starting_after=v1.eyJpZCI6Mz1zODQyMH0%3D"
    )
    try:
        seen = _with_urlopen(
            lambda: snyk.main(["issues", "--org", "o", "--next", relative_next])
        )
    finally:
        if old_token is None:
            os.environ.pop("SNYK_TOKEN", None)
        else:
            os.environ["SNYK_TOKEN"] = old_token
    expected = f"{snyk._api()}{relative_next}"
    assert seen == [expected]
    # querystring must survive byte-for-byte, no re-encoding of the cursor
    assert seen[0].endswith(
        "starting_after=v1.eyJpZCI6Mz1zODQyMH0%3D"
    )


def test_get_relative_path_with_params_still_encodes() -> None:
    seen = _with_urlopen(
        lambda: snyk._get(
            "/orgs/o/issues", {"version": "2026-03-25"}, "token-for-test"
        )
    )
    assert seen == [f"{snyk._api()}/orgs/o/issues?version=2026-03-25"]


def test_projects_expand_target_mapping() -> None:
    payload = {
        "jsonapi": {"version": "1.0"},
        "data": [
            {
                "id": "project-1",
                "type": "project",
                "attributes": {
                    "name": "api",
                    "origin": "github",
                    "target_reference": "main",
                    "target_file": "package.json",
                },
                "relationships": {
                    "target": {
                        "data": {
                            "id": "target-1",
                            "type": "target",
                            "attributes": {
                                "display_name": "org/repo",
                                "url": "https://github.com/org/repo",
                            },
                        }
                    }
                },
                "meta": {},
            }
        ],
        "links": {"self": "https://api.snyk.io/rest/orgs/o/projects"},
    }
    assert snyk._project_rows(payload) == [
        (
            "project-1",
            "api",
            "github",
            "main",
            "package.json",
            "org/repo",
            "https://github.com/org/repo",
        )
    ]


def test_request_params() -> None:
    args = snyk.build_parser().parse_args(
        [
            "issues",
            "--group",
            "g",
            "--limit",
            "1",
            "--severity",
            "high",
            "--severity",
            "critical",
            "--status",
            "open",
            "--type",
            "package_vulnerability",
            "--ignored",
            "false",
            "--scan-item-id",
            "p1",
            "--scan-item-type",
            "project",
            "--updated-after",
            "2026-01-01T00:00:00Z",
        ]
    )
    path, params = snyk._request(args)
    assert path == "/groups/g/issues"
    assert params["limit"] == 10
    assert params["effective_severity_level[]"] == ["high", "critical"]
    assert params["status[]"] == ["open"]
    assert params["type"] == "package_vulnerability"
    assert params["ignored"] == "false"
    assert params["scan_item.id"] == "p1"
    assert params["scan_item.type"] == "project"
    assert params["updated_after"] == "2026-01-01T00:00:00Z"


def test_url_uses_array_params() -> None:
    url = snyk._url(
        "/orgs/o/issues",
        {"version": "2026-03-25", "effective_severity_level[]": ["high"]},
    )
    query = urllib.parse.urlparse(url).query
    assert "effective_severity_level%5B%5D=high" in query


def test_http_error_does_not_echo_raw_body() -> None:
    text = _stderr_from_error(b"proxy echoed Authorization: token secret")
    assert text.strip() == "HTTP 403 Forbidden"
    assert "Authorization" not in text
    text = _stderr_from_error(
        b'{"errors":[{"title":"fallback title"},{"detail":"vendor detail"}]}'
    )
    assert "fallback title" in text
    assert "vendor detail" in text


def test_non_json_200_exits_cleanly() -> None:
    html = (b"<html><body>captive portal. "
            b"Authorization: token supersecrettoken</body></html>")
    old_urlopen = snyk.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> io.BytesIO:
        del timeout
        return io.BytesIO(html)

    snyk.urllib.request.urlopen = fake_urlopen
    try:
        try:
            snyk._get("/self", {"version": snyk.API_VERSION}, "token")
        except SystemExit as err:
            assert err.code != 0
            assert "supersecrettoken" not in str(err)
            assert "Authorization" not in str(err)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        snyk.urllib.request.urlopen = old_urlopen


if __name__ == "__main__":
    tests = [
        test_issue_prioritization_projection,
        test_snyk_problem_fallback,
        test_limit_clamping,
        test_token_missing_exits,
        test_next_url_fetched_verbatim,
        test_next_relative_cursor_fetched_verbatim,
        test_get_relative_path_with_params_still_encodes,
        test_projects_expand_target_mapping,
        test_request_params,
        test_url_uses_array_params,
        test_http_error_does_not_echo_raw_body,
        test_non_json_200_exits_cleanly,
    ]
    for test in tests:
        with redirect_stdout(io.StringIO()):
            test()
    print("ok")
