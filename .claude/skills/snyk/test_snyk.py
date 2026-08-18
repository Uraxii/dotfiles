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
            "-",
            "deployed,loaded_package",
            "function,package",
            True,
            "-",
        )
    ]


def test_risk_score_model_projected() -> None:
    payload = _issue_payload()
    payload["data"][0]["attributes"]["risk"]["score"]["model"] = "riskScore"
    assert snyk._issue_rows(payload)[0][6] == "riskScore"


def test_scan_item_id_projected_from_relationship() -> None:
    payload = _issue_payload()
    payload["data"][0]["relationships"] = {
        "scan_item": {"data": {"id": "proj-1", "type": "project"}}
    }
    assert snyk._issue_rows(payload)[0][-1] == "proj-1"


def test_risk_factors_absent_vs_empty() -> None:
    # key wholly absent -> unentitled tenant, not "no risk found"
    assert snyk._risk_factors({}) == "n/a"
    # key present but empty -> genuinely no factors
    assert snyk._risk_factors({"risk": {"factors": []}}) == "-"


def test_reachability_absent_vs_empty() -> None:
    assert snyk._reachability({}) == "n/a"
    assert snyk._reachability({"coordinates": []}) == "-"


def test_snyk_problem_fallback() -> None:
    payload = _issue_payload()
    payload["data"][0]["attributes"]["problems"] = [{"id": "SNYK-JS-THING-1"}]
    assert snyk._issue_rows(payload)[0][4] == "SNYK-JS-THING-1"


def test_limit_valid_values_pass_through_unclamped() -> None:
    assert snyk._check_limit("orgs", 20) == 20
    assert snyk._check_limit("targets", 1) == 1
    assert snyk._check_limit("findings", 100) == 100


def test_limit_out_of_range_rejected_not_clamped() -> None:
    for command, value in (
        ("orgs", 1),      # below 10, not a multiple of 10
        ("issues", 500),  # above 100
        ("targets", 0),   # below 1
        ("targets", 101),  # above 100
    ):
        try:
            snyk._check_limit(command, value)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"expected rejection for {command}={value}")


def test_limit_multiple_of_ten_enforced_for_step_endpoints() -> None:
    for command in ("orgs", "projects", "issues"):
        try:
            snyk._check_limit(command, 25)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"expected rejection for {command}=25")
    # targets/findings have no step, 25 is fine
    assert snyk._check_limit("targets", 25) == 25
    assert snyk._check_limit("findings", 25) == 25


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
            "20",
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
    assert params["limit"] == 20
    assert params["type"] == "package_vulnerability"
    assert params["ignored"] == "false"
    assert params["scan_item.id"] == "p1"
    assert params["scan_item.type"] == "project"
    assert params["updated_after"] == "2026-01-01T00:00:00Z"


def test_severity_wire_form_is_one_comma_joined_param() -> None:
    # style: form, explode: false -> effective_severity_level=high,critical
    args = snyk.build_parser().parse_args(
        ["issues", "--group", "g", "--severity", "high", "--severity",
         "critical"]
    )
    _, params = snyk._request(args)
    assert params["effective_severity_level"] == "high,critical"
    assert "effective_severity_level[]" not in params
    query = urllib.parse.urlparse(
        snyk._url("/groups/g/issues", params)
    ).query
    assert "effective_severity_level=high%2Ccritical" in query


def test_status_wire_form_is_one_comma_joined_param() -> None:
    args = snyk.build_parser().parse_args(
        ["issues", "--group", "g", "--status", "open", "--status",
         "resolved"]
    )
    _, params = snyk._request(args)
    assert params["status"] == "open,resolved"
    assert "status[]" not in params


def test_target_id_repeated_key() -> None:
    # target_id declares neither style nor explode -> explode: true (default)
    org = "11111111-1111-1111-1111-111111111111"
    args = snyk.build_parser().parse_args(
        ["projects", "--org", org, "--target-id", "uuid1", "--target-id",
         "uuid2"]
    )
    _, params = snyk._request(args)
    assert params["target_id"] == ["uuid1", "uuid2"]
    query = urllib.parse.urlparse(
        snyk._url(f"/orgs/{org}/projects", params)
    ).query
    assert "target_id=uuid1&target_id=uuid2" in query


def test_origins_wire_form_is_one_comma_joined_param() -> None:
    org = "11111111-1111-1111-1111-111111111111"
    args = snyk.build_parser().parse_args(
        ["projects", "--org", org, "--origin", "github", "--origin", "cli"]
    )
    _, params = snyk._request(args)
    assert params["origins"] == "github,cli"
    assert "origins[]" not in params


def test_targets_always_sends_exclude_empty_false_by_default() -> None:
    org = "11111111-1111-1111-1111-111111111111"
    args = snyk.build_parser().parse_args(["targets", "--org", org])
    _, params = snyk._request(args)
    assert params["exclude_empty"] == "false"


def test_targets_exclude_empty_overridable() -> None:
    org = "11111111-1111-1111-1111-111111111111"
    args = snyk.build_parser().parse_args(
        ["targets", "--org", org, "--exclude-empty", "true"]
    )
    _, params = snyk._request(args)
    assert params["exclude_empty"] == "true"


def test_next_cursor_unwraps_dict_form_href() -> None:
    # links.next is oneOf [string, {href, meta}]; object form must not
    # print as a raw Python dict, and must be usable as a --next value.
    payload = {"links": {"next": {"href": "/orgs/o/issues?limit=20",
                                   "meta": {}}}}
    assert snyk._next_cursor(payload) == "/orgs/o/issues?limit=20"


def test_next_cursor_bare_string_form() -> None:
    payload = {"links": {"next": "/orgs/o/issues?limit=20"}}
    assert snyk._next_cursor(payload) == "/orgs/o/issues?limit=20"


def test_next_cursor_absent() -> None:
    assert snyk._next_cursor({"links": {}}) is None
    assert snyk._next_cursor({}) is None


def test_api_host_strips_trailing_rest_suffix() -> None:
    old_host = os.environ.get("SNYK_API_HOST")
    os.environ["SNYK_API_HOST"] = "https://api.eu.snyk.io/rest"
    try:
        assert snyk._api() == "https://api.eu.snyk.io/rest"
    finally:
        if old_host is None:
            os.environ.pop("SNYK_API_HOST", None)
        else:
            os.environ["SNYK_API_HOST"] = old_host


def test_org_slug_rejected_not_uuid() -> None:
    args = snyk.build_parser().parse_args(
        ["projects", "--org", "not-a-uuid-slug"]
    )
    try:
        snyk._validate_scope(args)
    except SystemExit as err:
        assert "orgs --slug" in str(err)
    else:
        raise AssertionError("expected SystemExit")


def test_scan_item_id_and_type_must_be_paired() -> None:
    args = snyk.build_parser().parse_args(
        ["issues", "--group", "g", "--scan-item-id", "p1"]
    )
    try:
        snyk._validate_scope(args)
    except SystemExit as err:
        assert "--scan-item-id and --scan-item-type" in str(err)
    else:
        raise AssertionError("expected SystemExit")


def test_next_alone_needs_no_scope_args() -> None:
    old_token = os.environ.get("SNYK_TOKEN")
    os.environ["SNYK_TOKEN"] = "token-for-test"
    next_url = (
        "https://api.snyk.io/rest/orgs/o/issues?"
        "version=2026-03-25&starting_after=abc&limit=20"
    )
    try:
        seen = _with_urlopen(
            lambda: snyk.main(["issues", "--next", next_url])
        )
    finally:
        if old_token is None:
            os.environ.pop("SNYK_TOKEN", None)
        else:
            os.environ["SNYK_TOKEN"] = old_token
    assert seen == [next_url]


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
        test_risk_score_model_projected,
        test_scan_item_id_projected_from_relationship,
        test_risk_factors_absent_vs_empty,
        test_reachability_absent_vs_empty,
        test_snyk_problem_fallback,
        test_limit_valid_values_pass_through_unclamped,
        test_limit_out_of_range_rejected_not_clamped,
        test_limit_multiple_of_ten_enforced_for_step_endpoints,
        test_token_missing_exits,
        test_next_url_fetched_verbatim,
        test_next_relative_cursor_fetched_verbatim,
        test_get_relative_path_with_params_still_encodes,
        test_projects_expand_target_mapping,
        test_request_params,
        test_severity_wire_form_is_one_comma_joined_param,
        test_status_wire_form_is_one_comma_joined_param,
        test_target_id_repeated_key,
        test_origins_wire_form_is_one_comma_joined_param,
        test_targets_always_sends_exclude_empty_false_by_default,
        test_targets_exclude_empty_overridable,
        test_next_cursor_unwraps_dict_form_href,
        test_next_cursor_bare_string_form,
        test_next_cursor_absent,
        test_api_host_strips_trailing_rest_suffix,
        test_org_slug_rejected_not_uuid,
        test_scan_item_id_and_type_must_be_paired,
        test_next_alone_needs_no_scope_args,
        test_http_error_does_not_echo_raw_body,
        test_non_json_200_exits_cleanly,
    ]
    for test in tests:
        with redirect_stdout(io.StringIO()):
            test()
    print("ok")
