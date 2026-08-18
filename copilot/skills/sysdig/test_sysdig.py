"""Offline tests for sysdig.py."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import urllib.error
import urllib.parse
from pathlib import Path

_SKILL_DIR = Path(__file__).parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

import sysdig


def _http_error(body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://example.invalid", 403, "Forbidden", {}, io.BytesIO(body)
    )


def _stderr_from_error(body: bytes) -> str:
    old_urlopen = sysdig.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        raise _http_error(body)

    sysdig.urllib.request.urlopen = fake_urlopen
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            try:
                sysdig._get("/path", {}, "token", "https://api.us2.sysdig.com")
            except SystemExit as err:
                assert err.code == 1
            else:
                raise AssertionError("expected SystemExit")
    finally:
        sysdig.urllib.request.urlopen = old_urlopen
    return stderr.getvalue()


def _query(url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


def test_cursor_query_and_next_token() -> None:
    url = sysdig._url(
        "https://api.us2.sysdig.com",
        "/secure/vulnerability/v1/runtime-results",
        {"cursor": "abc", "limit": 50, "filter": "hasRunningVulns=true"},
    )
    query = _query(url)
    payload = {"data": [], "page": {"next": "def", "total": 2}}
    assert query["cursor"] == ["abc"]
    assert query["limit"] == ["50"]
    assert query["filter"] == ["hasRunningVulns=true"]
    assert payload["page"]["next"] == "def"


def test_cspm_page_number_uses_page_next() -> None:
    url = sysdig._url(
        "https://api.us2.sysdig.com",
        "/secure/inventory/v1/resources",
        {
            "filter": "cluster=\"prod\"",
            "withEnrichedContainers": "true",
            "pageNumber": 2,
            "pageSize": 50,
        },
    )
    query = _query(url)
    payload = {"data": [{}], "page": {"next": 3, "total": 10}}
    stderr = io.StringIO()
    assert query["pageNumber"] == ["2"]
    assert query["pageSize"] == ["50"]
    assert query["withEnrichedContainers"] == ["true"]
    with contextlib.redirect_stderr(stderr):
        sysdig._show_cspm_page(payload, 2, 50)
    assert stderr.getvalue() == "next pageNumber: 3\n"


def test_zones_filter_path_and_wrapper() -> None:
    url = sysdig._url(
        sysdig._host("us2", "/platform/v1/zones"),
        "/platform/v1/zones",
        {"filter": sysdig._zone_filter("prod")},
    )
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parts.query)
    payload = {"zones": [{"id": "z1", "name": "prod", "type": "zone"}]}
    assert parts.netloc == "us2.app.sysdig.com"
    assert parts.path == "/platform/v1/zones"
    assert query["filter"] == ["name:prod"]
    assert sysdig._basic_rows(payload) == [("z1", "prod", "zone", None)]


def test_basic_rows_falls_back_to_pull_string() -> None:
    payload = {"data": [{
        "resultId": "r2",
        "pullString": "ghcr.io/acme/api:1.2",
        "type": "containerImage",
        "policyEvaluationResult": "passed",
    }]}
    assert sysdig._basic_rows(payload) == [
        ("r2", "ghcr.io/acme/api:1.2", "containerImage", "passed")
    ]


def test_host_by_path_family() -> None:
    assert sysdig._host("us2", "/secure/foo") == "https://api.us2.sysdig.com"
    assert sysdig._host("eu1", "/api/foo") == "https://eu1.app.sysdig.com"
    assert sysdig._host("us3", "/platform/foo") == "https://app.us3.sysdig.com"
    assert sysdig._host("us1", "/api/foo") == "https://secure.sysdig.com"
    assert "jp1" in sysdig.REGIONS


def test_runtime_rows_project_running_and_scope() -> None:
    payload = {
        "data": [{
            "resultId": "r1",
            "mainAssetName": "api",
            "policyEvaluationResult": "failed",
            "runningVulnTotalBySeverity": {"critical": 2},
            "vulnTotalBySeverity": {"critical": 10},
            "scope": {
                "asset.type": "containerImage",
                "kubernetes.cluster.name": "prod",
                "kubernetes.namespace.name": "orders",
            },
        }],
        "page": {"next": None, "total": 1},
    }
    assert sysdig._runtime_rows(payload) == [(
        "r1",
        "api",
        "containerImage",
        "prod",
        "orders",
        "critical:2,high:0,medium:0,low:0,negligible:0",
        "critical:10,high:0,medium:0,low:0,negligible:0",
        "failed",
    )]


def test_running_filter_composes() -> None:
    args = sysdig.build_parser().parse_args([
        "--host", "us2", "runtime", "--filter", "asset.type=\"image\"",
        "--running", "--cluster", "prod",
    ])
    assert sysdig._runtime_filter(args) == (
        "asset.type=\"image\" and kubernetes.cluster.name=\"prod\" "
        "and hasRunningVulns=true"
    )


def test_result_rows_project_detail_vuln_fields() -> None:
    payload = {"result": {
        "packages": {
            "pkg:deb/debian/openssl@3.0.1": {
                "name": "openssl",
                "version": "3.0.1",
                "vulnerabilitiesRefs": ["CVE-1"],
            },
        },
        "vulnerabilities": {
            "CVE-1": {
                "name": "CVE-1",
                "severity": "critical",
                "exploitable": True,
                "exploit": True,
                "acceptedRisks": [],
                "suggestedFix": "3.0.2",
            },
        },
    }}
    assert sysdig._result_rows(payload) == [(
        "openssl", "3.0.1", "CVE-1", "critical", True, True, [], "3.0.2"
    )]


def test_limit_clamping() -> None:
    assert sysdig._limit(2000, sysdig.RUNTIME_MAX_LIMIT) == 1000
    assert sysdig._limit(2000, sysdig.REGISTRY_MAX_LIMIT) == 1000
    assert sysdig._limit(0, sysdig.RUNTIME_MAX_LIMIT) == 1
    args = sysdig.build_parser().parse_args(["--host", "us2", "registry"])
    assert args.limit == 1000


def test_token_missing_exits() -> None:
    old = os.environ.pop("SYSDIG_API_TOKEN", None)
    try:
        try:
            sysdig._token()
        except SystemExit as err:
            assert "SYSDIG_API_TOKEN" in str(err)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        if old is not None:
            os.environ["SYSDIG_API_TOKEN"] = old


def test_http_error_does_not_echo_raw_body() -> None:
    text = _stderr_from_error(b"proxy echoed Authorization: Bearer secret")
    assert text.strip() == "HTTP 403 Forbidden"
    assert "Authorization" not in text
    text = _stderr_from_error(
        json.dumps({"message": "vendor message"}).encode()
    )
    assert "vendor message" in text


def test_non_json_200_exits_cleanly() -> None:
    html = (b"<html><body>captive portal. "
            b"Authorization: Bearer supersecrettoken</body></html>")
    old_urlopen = sysdig.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> io.BytesIO:
        del timeout
        return io.BytesIO(html)

    sysdig.urllib.request.urlopen = fake_urlopen
    try:
        try:
            sysdig._get("/path", {}, "token", "https://api.us2.sysdig.com")
        except SystemExit as err:
            assert err.code != 0
            assert "supersecrettoken" not in str(err)
            assert "Authorization" not in str(err)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        sysdig.urllib.request.urlopen = old_urlopen


if __name__ == "__main__":
    test_cursor_query_and_next_token()
    test_cspm_page_number_uses_page_next()
    test_zones_filter_path_and_wrapper()
    test_basic_rows_falls_back_to_pull_string()
    test_host_by_path_family()
    test_runtime_rows_project_running_and_scope()
    test_running_filter_composes()
    test_result_rows_project_detail_vuln_fields()
    test_limit_clamping()
    test_token_missing_exits()
    test_http_error_does_not_echo_raw_body()
    test_non_json_200_exits_cleanly()
    print("ok")
