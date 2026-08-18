"""Offline tests for ox_security.py."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import urllib.error
from pathlib import Path

_SKILL_DIR = Path(__file__).parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

import ox_security


def _http_error(body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://example.invalid", 403, "Forbidden", {}, io.BytesIO(body)
    )


def _exit_text(fn: object, *args: object) -> str:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        try:
            fn(*args)
        except SystemExit as error:
            return f"{error}{stderr.getvalue()}"
    raise AssertionError("expected SystemExit")


def _stderr_from_error(body: bytes) -> str:
    old_key = os.environ.get("OX_API_KEY")
    old_urlopen = ox_security.urllib.request.urlopen
    os.environ["OX_API_KEY"] = "token"

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        raise _http_error(body)

    ox_security.urllib.request.urlopen = fake_urlopen
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            try:
                ox_security._post("GetIssues", ox_security.ISSUES_QUERY, {})
            except SystemExit as error:
                assert error.code == 1
            else:
                raise AssertionError("expected SystemExit")
    finally:
        ox_security.urllib.request.urlopen = old_urlopen
        if old_key is None:
            os.environ.pop("OX_API_KEY", None)
        else:
            os.environ["OX_API_KEY"] = old_key
    return stderr.getvalue()


def test_query_documents_use_verified_names() -> None:
    assert "getIssues(getIssuesInput:" in ox_security.ISSUES_QUERY
    assert "$getIssuesInput: IssuesInput" in ox_security.ISSUES_QUERY
    assert "IssuesInput.limit is Int!" in ox_security.ISSUES_QUERY
    assert "GetApplicationsInput.limit is Int" in ox_security.APPLICATIONS_QUERY
    assert "getApplications(getApplicationsInput:" in ox_security.APPLICATIONS_QUERY
    assert "$getApplicationsInput: GetApplicationsInput" in ox_security.APPLICATIONS_QUERY
    assert "getapps" not in ox_security.APPLICATIONS_QUERY
    assert " oxSeverity" not in ox_security.ISSUES_QUERY
    assert " riskStatus" not in ox_security.ISSUES_QUERY
    assert " title" not in ox_security.ISSUES_QUERY
    assert "      issueId" in ox_security.ISSUES_QUERY
    assert "      severity" in ox_security.ISSUES_QUERY
    assert "      id" not in ox_security.ISSUES_QUERY
    assert "      cve" not in ox_security.ISSUES_QUERY
    assert "scaVulnerabilities { cve epss percentile exploitInTheWild }" in (
        ox_security.ISSUES_QUERY
    )
    assert "      appId" in ox_security.APPLICATIONS_QUERY


def test_issues_input_limit_is_always_sent_and_required() -> None:
    args = ox_security.build_parser().parse_args(["issues", "--limit", "7"])
    assert ox_security._issue_input(args)["limit"] == 7
    assert "IssuesInput.limit is Int!" in ox_security.ISSUES_QUERY
    assert "GetApplicationsInput.limit is Int" in ox_security.APPLICATIONS_QUERY


def test_severity_maps_to_filters_criticality_and_sends_no_search() -> None:
    args = ox_security.build_parser().parse_args([
        "issues", "--severity", "Critical", "--app", "Org/repo",
    ])
    data = ox_security._issue_input(args)
    assert data["filters"] == {
        "criticality": ["Critical"],
        "apps": ["Org/repo"],
    }
    assert "search" not in data


def test_invalid_severity_exits_nonzero_and_names_legal_members() -> None:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        try:
            ox_security.build_parser().parse_args([
                "issues", "--severity", "critical",
            ])
        except SystemExit as error:
            assert error.code != 0
        else:
            raise AssertionError("expected SystemExit")
    for member in ox_security.CRITICALITY_CHOICES:
        assert member in stderr.getvalue()


def test_app_maps_to_filters_apps() -> None:
    args = ox_security.build_parser().parse_args(["issues", "--app", "Org/repo"])
    data = ox_security._issue_input(args)
    assert data["filters"] == {"apps": ["Org/repo"]}


def test_repeated_filter_flag_appends_into_one_list() -> None:
    args = ox_security.build_parser().parse_args([
        "issues", "--filter", "tags=a", "--filter", "tags=b",
    ])
    data = ox_security._issue_input(args)
    assert data["filters"] == {"tags": ["a", "b"]}


def test_unknown_filter_field_exits_nonzero() -> None:
    message = _exit_text(
        ox_security._parse_filters, ["fixedIssues=true"],
    )
    assert "fixedIssues" in message


def test_no_variables_payload_contains_page_or_filter_search() -> None:
    issue_args = ox_security.build_parser().parse_args([
        "issues", "--severity", "Critical", "--app", "Org/repo",
    ])
    app_args = ox_security.build_parser().parse_args(["apps", "--search", "api"])
    for data in (ox_security._issue_input(issue_args), ox_security._app_input(app_args)):
        assert "page" not in data
        assert "filterSearch" not in data


def test_issue_search_uses_top_level_search_not_autocomplete() -> None:
    args = ox_security.build_parser().parse_args(["issues", "--search", "CVE"])
    data = ox_security._issue_input(args)
    assert data["topLevelSearch"] == "CVE"
    assert "search" not in data


def test_apps_search_is_a_plain_string() -> None:
    args = ox_security.build_parser().parse_args(["apps", "--search", "api"])
    data = ox_security._app_input(args)
    assert data["search"] == "api"
    assert "filterSearch" not in data


def test_app_flows_target_one_app_id() -> None:
    args = ox_security.build_parser().parse_args(["app-flows", "app-1"])
    assert args.appId == "app-1"


def test_application_rows_read_applications_not_apps() -> None:
    payload = {"data": {"getApplications": {
        "applications": [{"appId": "a1", "repoName": "api", "branch": "main",
                          "deployedProd": True, "businessPriority": "high",
                          "matchedProjects": [{"toolName": "Snyk"}]}],
        "apps": [{"appId": "wrong"}],
        "total": 1,
        "totalFilteredApps": 1,
    }}}
    assert ox_security._app_rows(payload) == [
        ("a1", "api", "main", True, "high", "Snyk"),
    ]


def test_vendor_pr_typo_is_projected() -> None:
    assert "prDeatils" in ox_security.ISSUES_QUERY
    assert "prDetails" not in ox_security.ISSUES_QUERY
    assert "prDeatils { prURL prStatus }" in ox_security.ISSUES_QUERY
    assert "prDeatils { url status }" not in ox_security.ISSUES_QUERY


def test_default_authorization_header_is_bare_key() -> None:
    old_bearer = os.environ.pop("OX_AUTH_BEARER", None)
    try:
        assert ox_security._headers("secret")["Authorization"] == "secret"
    finally:
        if old_bearer is not None:
            os.environ["OX_AUTH_BEARER"] = old_bearer


def test_bearer_authorization_header_is_opt_in() -> None:
    old_bearer = os.environ.get("OX_AUTH_BEARER")
    os.environ["OX_AUTH_BEARER"] = "1"
    try:
        assert ox_security._headers("secret")["Authorization"] == "Bearer secret"
    finally:
        if old_bearer is None:
            os.environ.pop("OX_AUTH_BEARER", None)
        else:
            os.environ["OX_AUTH_BEARER"] = old_bearer


def test_operation_allowlist_rejects_unknown_name() -> None:
    message = _exit_text(ox_security._post, "NotAllowlisted", "query X { x }", {})
    assert "refusing non-read-only OX operation" in message


def test_issue_priority_projection() -> None:
    payload = {"data": {"getIssues": {"issues": [{
        "issueId": "i1",
        "name": "Secret in code",
        "appName": "api",
        "severity": "Critical",
        "originalToolSeverity": "High",
        "sourceTools": ["Snyk"],
        "isFixAvailable": True,
        "isFixApplied": False,
        "app": {"businessPriority": "high"},
        "scaVulnerabilities": [{
            "epss": 0.91,
            "percentile": 99,
            "exploitInTheWild": True,
            "cve": "CVE-2026-0001",
        }],
    }]}}}
    assert ox_security._issue_rows(payload) == [
        ("Secret in code", "api", "Critical", "High", ["Snyk"], "high",
         0.91, 99, True, True),
    ]


def test_field_rounds_float_to_one_decimal() -> None:
    assert ox_security._field(74.77083333333333) == "74.8"


def test_field_leaves_int_untouched() -> None:
    assert ox_security._field(74) == "74"


def test_field_bool_is_not_treated_as_float() -> None:
    assert ox_security._field(True) == "yes"


def test_app_flows_reads_singular_application_flow() -> None:
    payload = {"data": {"getApplications": {"applications": [{
        "repoName": "api",
        "branch": "main",
        "deployedProd": True,
        "applicationFlows": {
            "repository": [{"type": "repo", "system": "Azure Repos"}],
            "cicdInfo": [{"type": "build", "system": "Azure Pipelines"}],
            "artifacts": [{"hash": "sha256:abc"}],
            "kubernetes": [{"name": "api-prod"}],
            "cloudDeployments": [{"imageName": "api:latest"}],
        },
    }]}}}
    assert ox_security._flow_rows(payload) == [
        (
            "api",
            "main",
            True,
            "Azure Repos",
            "Azure Pipelines",
            "sha256:abc",
            "api-prod",
            "api:latest",
        ),
    ]


def test_graphql_errors_exit() -> None:
    message = _exit_text(ox_security._raise_graphql_errors, {"errors": [
        {"message": "bad field"},
    ]})
    assert "bad field" in message


def test_token_missing_exits() -> None:
    os.environ.pop("OX_API_KEY", None)
    message = _exit_text(ox_security._token)
    assert "OX_API_KEY" in message


def test_http_error_does_not_echo_raw_body() -> None:
    text = _stderr_from_error(b"proxy echoed Authorization: Bearer secret")
    assert text.strip() == "HTTP 403 Forbidden"
    assert "Authorization" not in text
    text = _stderr_from_error(
        json.dumps({"errors": [{"message": "vendor message"}]}).encode()
    )
    assert "vendor message" in text


def test_non_json_200_exits_cleanly() -> None:
    html = (b"<html><body>captive portal. "
            b"Authorization: Bearer supersecrettoken</body></html>")
    old_key = os.environ.get("OX_API_KEY")
    old_urlopen = ox_security.urllib.request.urlopen
    os.environ["OX_API_KEY"] = "token"

    def fake_urlopen(_request: object, timeout: int) -> io.BytesIO:
        del timeout
        return io.BytesIO(html)

    ox_security.urllib.request.urlopen = fake_urlopen
    try:
        try:
            ox_security._post("GetIssues", ox_security.ISSUES_QUERY, {})
        except SystemExit as err:
            assert err.code != 0
            assert "supersecrettoken" not in str(err)
            assert "Authorization" not in str(err)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        ox_security.urllib.request.urlopen = old_urlopen
        if old_key is None:
            os.environ.pop("OX_API_KEY", None)
        else:
            os.environ["OX_API_KEY"] = old_key


if __name__ == "__main__":
    test_query_documents_use_verified_names()
    test_issues_input_limit_is_always_sent_and_required()
    test_severity_maps_to_filters_criticality_and_sends_no_search()
    test_invalid_severity_exits_nonzero_and_names_legal_members()
    test_app_maps_to_filters_apps()
    test_repeated_filter_flag_appends_into_one_list()
    test_unknown_filter_field_exits_nonzero()
    test_no_variables_payload_contains_page_or_filter_search()
    test_issue_search_uses_top_level_search_not_autocomplete()
    test_apps_search_is_a_plain_string()
    test_app_flows_target_one_app_id()
    test_application_rows_read_applications_not_apps()
    test_vendor_pr_typo_is_projected()
    test_default_authorization_header_is_bare_key()
    test_bearer_authorization_header_is_opt_in()
    test_operation_allowlist_rejects_unknown_name()
    test_issue_priority_projection()
    test_field_rounds_float_to_one_decimal()
    test_field_leaves_int_untouched()
    test_field_bool_is_not_treated_as_float()
    test_app_flows_reads_singular_application_flow()
    test_graphql_errors_exit()
    test_token_missing_exits()
    test_http_error_does_not_echo_raw_body()
    test_non_json_200_exits_cleanly()
    print("ok")
