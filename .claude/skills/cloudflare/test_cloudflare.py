"""Offline tests for cloudflare.py."""
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

import cloudflare


def envelope(result: object, info: dict | None = None) -> dict:
    payload = {"result": result, "success": True, "errors": [], "messages": []}
    if info is not None:
        payload["result_info"] = info
    return payload


def params_for(argv: list[str]) -> tuple[str, dict[str, object]]:
    args = cloudflare.build_parser().parse_args(argv)
    path, params, _header, _rows = cloudflare._request(args)
    return path, cloudflare._clean(params)


def _http_error(body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://example.invalid", 403, "Forbidden", {}, io.BytesIO(body)
    )


def _stderr_from_error(body: bytes) -> str:
    old_urlopen = cloudflare.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        raise _http_error(body)

    cloudflare.urllib.request.urlopen = fake_urlopen
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            try:
                cloudflare._get("/zones", {}, "token")
            except SystemExit as err:
                assert err.code == 1
            else:
                raise AssertionError("expected SystemExit")
    finally:
        cloudflare.urllib.request.urlopen = old_urlopen
    return stderr.getvalue()


def test_offset_pagination_params() -> None:
    path, params = params_for(["accounts", "--page", "3", "--per-page", "10"])
    query = urllib.parse.urlencode(params)
    assert path == "/accounts"
    assert query == "page=3&per_page=10"


def test_zones_offset_pagination_params() -> None:
    path, params = params_for(["zones", "--page", "2", "--per-page", "99"])
    query = urllib.parse.urlencode(params)
    assert path == "/zones"
    assert query == "page=2&per_page=50"


def test_ruleset_cursor_pagination_params() -> None:
    path, params = params_for([
        "rulesets", "--zone", "z1", "--cursor", "abc", "--per-page", "10",
    ])
    query = urllib.parse.urlencode(params)
    assert path == "/zones/z1/rulesets"
    assert query == "cursor=abc&per_page=10"


def test_page_info_schemes_read_different_places() -> None:
    offset = envelope([], {"count": 1, "page": 2, "per_page": 5,
                           "total_count": 9, "total_pages": 2})
    cursor = envelope([], {"cursors": {"after": "next-token"}})
    assert offset["result_info"]["page"] == 2
    assert cursor["result_info"]["cursors"]["after"] == "next-token"


def _stderr_from_show_page(payload: dict) -> str:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        cloudflare._show_page(payload)
    return stderr.getvalue()


def test_show_page_reads_flat_cursor() -> None:
    payload = envelope([], {"cursor": "flat-token"})
    assert "flat-token" in _stderr_from_show_page(payload)


def test_show_page_reads_nested_cursor() -> None:
    payload = envelope([], {"cursors": {"after": "nested-token"}})
    assert "nested-token" in _stderr_from_show_page(payload)


def test_show_page_guards_missing_page_fields() -> None:
    payload = envelope([], {"count": 5})
    assert _stderr_from_show_page(payload) == ""


def test_unsuccessful_envelope_exits_with_error() -> None:
    payload = {"result": [], "success": False,
               "errors": [{"message": "bad zone"}], "messages": []}
    try:
        cloudflare._check(payload)
    except SystemExit as err:
        assert str(err) == "bad zone"
    else:
        raise AssertionError("expected SystemExit")


def test_dns_proxied_projection_and_filter() -> None:
    path, params = params_for(["dns", "--zone", "z1", "--proxied", "false"])
    payload = envelope([{"name": "origin.example.com", "type": "A",
                         "content": "192.0.2.10", "proxied": False, "ttl": 1}])
    assert path == "/zones/z1/dns_records"
    assert params["proxied"] == "false"
    assert cloudflare._dns_rows(payload) == [
        ("origin.example.com", "A", "192.0.2.10", False, 1)
    ]


def test_waf_owasp_entrypoint_parse() -> None:
    payload = envelope({"rules": [
        {"action": "execute", "enabled": True, "action_parameters": {
            "id": cloudflare.OWASP_CORE_RULESET_ID,
            "overrides": {
                "categories": [
                    {"category": "paranoia-level-2", "enabled": True},
                    {"category": "paranoia-level-3", "enabled": False},
                ],
                "rules": [
                    {"id": cloudflare.SCORE_THRESHOLD_RULE_ID,
                     "score_threshold": 60},
                    {"id": "other-rule", "score_threshold": 10},
                ],
            },
        }},
    ]})
    assert cloudflare._waf_rows(payload) == [
        (cloudflare.OWASP_CORE_RULESET_ID, "OWASP Core Ruleset", "PL2", "Low",
         60, True),
    ]


def test_waf_non_owasp_execute_rule_emits_dashes() -> None:
    # Cloudflare Managed / Exposed Credentials rulesets: no paranoia/threshold
    # fields exist on these, so no defaults may be fabricated for them.
    payload = envelope({"rules": [
        {"action": "execute", "enabled": True, "action_parameters": {
            "id": "managed-2",
            "overrides": {"rules": [{"score_threshold": 40}]},
        }},
    ]})
    assert cloudflare._waf_rows(payload) == [
        ("managed-2", "-", "-", "-", "-", True),
    ]


def test_waf_disabled_rule_is_still_reported_with_state() -> None:
    payload = envelope({"rules": [
        {"action": "execute", "enabled": False, "action_parameters": {
            "id": cloudflare.OWASP_CORE_RULESET_ID,
            "overrides": {
                "categories": [
                    {"category": "paranoia-level-1", "enabled": True},
                ],
                "rules": [{"id": cloudflare.SCORE_THRESHOLD_RULE_ID,
                           "score_threshold": 40}],
            },
        }},
    ]})
    assert cloudflare._waf_rows(payload) == [
        (cloudflare.OWASP_CORE_RULESET_ID, "OWASP Core Ruleset", "PL1",
         "Medium", 40, False),
    ]


def test_score_threshold_pins_to_rule_id() -> None:
    rules = [
        {"id": "other-rule", "score_threshold": 10},
        {"id": cloudflare.SCORE_THRESHOLD_RULE_ID, "score_threshold": 25},
    ]
    assert cloudflare._score_threshold(rules) == 25
    assert cloudflare._score_threshold([{"id": "other-rule",
                                          "score_threshold": 10}]) == 40


def test_paranoia_handles_null_category() -> None:
    categories = [{"category": None, "enabled": True}]
    assert cloudflare._paranoia(categories) == "PL1"


def test_zone_rows_handles_null_account() -> None:
    payload = envelope([{"id": "z1", "name": "example.com", "status": "active",
                         "type": "full", "paused": False, "account": None}])
    assert cloudflare._zone_rows(payload) == [
        ("z1", "example.com", "active", "full", False, None)
    ]


def test_dns_per_page_clamp() -> None:
    _path, low = params_for(["dns", "--zone", "z1", "--per-page", "0"])
    _path, high = params_for(["dns", "--zone", "z1", "--per-page", "999999"])
    assert low["per_page"] == 1
    assert high["per_page"] == cloudflare.DNS_MAX_PER_PAGE


def test_per_page_clamping() -> None:
    _path, accounts = params_for(["accounts", "--per-page", "1"])
    _path, rulesets = params_for(["rulesets", "--account", "a1", "--per-page", "99"])
    assert accounts["per_page"] == 5
    assert rulesets["per_page"] == 50


def test_throttle_sleep_computation() -> None:
    assert round(cloudflare._sleep_needed(10.10, 10.00), 2) == 0.15
    assert cloudflare._sleep_needed(10.50, 10.00) == 0.0


def test_missing_token_exits() -> None:
    os.environ.pop("CLOUDFLARE_API_TOKEN", None)
    try:
        cloudflare._token()
    except SystemExit as err:
        assert "CLOUDFLARE_API_TOKEN" in str(err)
    else:
        raise AssertionError("expected SystemExit")


def test_http_error_does_not_echo_raw_body() -> None:
    text = _stderr_from_error(b"proxy echoed Authorization: Bearer secret")
    assert text.strip() == "HTTP 403 Forbidden"
    assert "Authorization" not in text
    text = _stderr_from_error(
        json.dumps({"errors": [{"message": "vendor message"}]}).encode()
    )
    assert "vendor message" in text


def test_waf_missing_entrypoint_gives_explanation() -> None:
    body = json.dumps({"errors": [{"code": 10003, "message":
        "could not find entrypoint ruleset in the "
        "http_request_firewall_managed phase"}]}).encode()
    old_urlopen = cloudflare.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        raise urllib.error.HTTPError(
            "https://example.invalid", 404, "Not Found", {}, io.BytesIO(body)
        )

    cloudflare.urllib.request.urlopen = fake_urlopen
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            try:
                cloudflare._get(
                    "/zones/ZONE_ID/rulesets/phases/"
                    "http_request_firewall_managed/entrypoint", {}, "token",
                )
            except SystemExit as err:
                assert err.code == 0
            else:
                raise AssertionError("expected SystemExit")
    finally:
        cloudflare.urllib.request.urlopen = old_urlopen
    text = stderr.getvalue()
    assert "rulesets" in text
    assert "could not find entrypoint ruleset" not in text
    assert "10003" not in text


def test_waf_missing_entrypoint_raw_stdout_is_json() -> None:
    body = json.dumps({"errors": [{"code": 10003, "message":
        "could not find entrypoint ruleset in the "
        "http_request_firewall_managed phase"}]}).encode()
    old_urlopen = cloudflare.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        raise urllib.error.HTTPError(
            "https://example.invalid", 404, "Not Found", {}, io.BytesIO(body)
        )

    cloudflare.urllib.request.urlopen = fake_urlopen
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            try:
                cloudflare._get(
                    "/zones/ZONE_ID/rulesets/phases/"
                    "http_request_firewall_managed/entrypoint", {}, "token",
                    raw=True,
                )
            except SystemExit as err:
                assert err.code == 0
            else:
                raise AssertionError("expected SystemExit")
    finally:
        cloudflare.urllib.request.urlopen = old_urlopen
    text = stdout.getvalue()
    assert text.strip() != ""
    payload = json.loads(text)
    assert payload["result"] is None
    assert payload["no_entrypoint_ruleset"] is True
    assert payload["phase"] == "http_request_firewall_managed"
    assert "could not find entrypoint ruleset" not in text
    assert "10003" not in text


def test_waf_missing_entrypoint_default_stdout_states_situation() -> None:
    body = json.dumps({"errors": [{"code": 10003, "message":
        "could not find entrypoint ruleset in the "
        "http_request_firewall_managed phase"}]}).encode()
    old_urlopen = cloudflare.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        raise urllib.error.HTTPError(
            "https://example.invalid", 404, "Not Found", {}, io.BytesIO(body)
        )

    cloudflare.urllib.request.urlopen = fake_urlopen
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            try:
                cloudflare._get(
                    "/zones/ZONE_ID/rulesets/phases/"
                    "http_request_firewall_managed/entrypoint", {}, "token",
                )
            except SystemExit as err:
                assert err.code == 0
            else:
                raise AssertionError("expected SystemExit")
    finally:
        cloudflare.urllib.request.urlopen = old_urlopen
    text = stdout.getvalue()
    assert text.strip() != ""
    assert "no entrypoint ruleset" in text
    assert "could not find entrypoint ruleset" not in text
    assert "10003" not in text


def test_429_retry_capped_sleep() -> None:
    calls = []

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                "https://example.invalid", 429, "Too Many Requests",
                {"Retry-After": "300"}, io.BytesIO(b"{}"),
            )
        return io.BytesIO(json.dumps(envelope([])).encode())

    sleeps = []
    old_urlopen = cloudflare.urllib.request.urlopen
    old_sleep = cloudflare.time.sleep
    cloudflare.urllib.request.urlopen = fake_urlopen
    cloudflare.time.sleep = lambda secs: sleeps.append(secs)
    try:
        payload = cloudflare._get("/zones", {}, "token")
    finally:
        cloudflare.urllib.request.urlopen = old_urlopen
        cloudflare.time.sleep = old_sleep
    assert len(calls) == 2
    assert sleeps[0] == cloudflare.MAX_RETRY_AFTER_SEC
    assert payload["success"] is True


def test_429_retry_preserves_raw_through_missing_entrypoint_404() -> None:
    body = json.dumps({"errors": [{"code": 10003, "message":
        "could not find entrypoint ruleset in the "
        "http_request_firewall_managed phase"}]}).encode()
    calls = []

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                "https://example.invalid", 429, "Too Many Requests",
                {"Retry-After": "1"}, io.BytesIO(b"{}"),
            )
        raise urllib.error.HTTPError(
            "https://example.invalid", 404, "Not Found", {}, io.BytesIO(body)
        )

    old_urlopen = cloudflare.urllib.request.urlopen
    old_sleep = cloudflare.time.sleep
    cloudflare.urllib.request.urlopen = fake_urlopen
    cloudflare.time.sleep = lambda secs: None
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            try:
                cloudflare._get(
                    "/zones/ZONE_ID/rulesets/phases/"
                    "http_request_firewall_managed/entrypoint", {}, "token",
                    raw=True,
                )
            except SystemExit as err:
                assert err.code == 0
            else:
                raise AssertionError("expected SystemExit")
    finally:
        cloudflare.urllib.request.urlopen = old_urlopen
        cloudflare.time.sleep = old_sleep
    assert len(calls) == 2
    text = stdout.getvalue()
    payload = json.loads(text)
    assert payload["no_entrypoint_ruleset"] is True


def test_non_json_200_exits_cleanly() -> None:
    html = (b"<html><body>captive portal. "
            b"Authorization: Bearer supersecrettoken</body></html>")
    old_urlopen = cloudflare.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> io.BytesIO:
        del timeout
        return io.BytesIO(html)

    cloudflare.urllib.request.urlopen = fake_urlopen
    try:
        try:
            cloudflare._get("/zones", {}, "token")
        except SystemExit as err:
            assert err.code != 0
            assert "supersecrettoken" not in str(err)
            assert "Authorization" not in str(err)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        cloudflare.urllib.request.urlopen = old_urlopen


if __name__ == "__main__":
    test_offset_pagination_params()
    test_zones_offset_pagination_params()
    test_ruleset_cursor_pagination_params()
    test_page_info_schemes_read_different_places()
    test_unsuccessful_envelope_exits_with_error()
    test_dns_proxied_projection_and_filter()
    test_waf_owasp_entrypoint_parse()
    test_per_page_clamping()
    test_throttle_sleep_computation()
    test_missing_token_exits()
    test_http_error_does_not_echo_raw_body()
    test_waf_missing_entrypoint_gives_explanation()
    test_waf_missing_entrypoint_raw_stdout_is_json()
    test_waf_missing_entrypoint_default_stdout_states_situation()
    test_429_retry_preserves_raw_through_missing_entrypoint_404()
    test_non_json_200_exits_cleanly()
    print("ok")
