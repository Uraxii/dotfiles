"""Offline tests for azure_devops.py."""
from __future__ import annotations

import base64
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

import azure_devops


def _http_error(body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://example.invalid", 403, "Forbidden", {}, io.BytesIO(body)
    )


EXPECTED = {
    "projects": ("dev.azure.com", "7.2-preview.4", "int32"),
    "repos": ("dev.azure.com", "7.2-preview.2", None),
    "items": ("dev.azure.com", "7.2-preview.1", None),
    "pipelines": ("dev.azure.com", "7.2-preview.1", "string"),
    "runs": ("dev.azure.com", "7.2-preview.1", None),
    "builds": ("dev.azure.com", "7.2-preview.8", "string"),
    "artifacts": ("dev.azure.com", "7.2-preview.5", None),
    "deployments": ("vsrm.dev.azure.com", "7.2-preview.2", "int32"),
    "releasedefs": ("vsrm.dev.azure.com", "7.2-preview.4", "string"),
    "release-env": ("vsrm.dev.azure.com", "7.1-preview.7", None),
    "environments": ("dev.azure.com", "7.1-preview.1", "string"),
    "k8s": ("dev.azure.com", "7.1-preview.1", None),
    "wiql": ("dev.azure.com", "7.2-preview.2", None),
}


def _args(*argv: str):
    return azure_devops.build_parser().parse_args(list(argv))


def _url(command: str, *argv: str) -> tuple[str, str, dict[str, object], object,
                                           str]:
    args = _args(command, *argv)
    return azure_devops._request_parts(args, "org")


def _stderr_from_error(body: bytes) -> str:
    old_urlopen = azure_devops.urllib.request.urlopen

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        raise _http_error(body)

    azure_devops.urllib.request.urlopen = fake_urlopen
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            try:
                azure_devops._fetch(
                    "https://dev.azure.com/org/_apis/projects",
                    "GET",
                    None,
                    "Bearer token",
                )
            except SystemExit as err:
                assert err.code == 1
            else:
                raise AssertionError("expected SystemExit")
    finally:
        azure_devops.urllib.request.urlopen = old_urlopen
    return stderr.getvalue()


def test_endpoint_table_versions_hosts_and_continuation_types() -> None:
    assert set(azure_devops.ENDPOINTS) == set(EXPECTED)
    for command, (host, version, token_type) in EXPECTED.items():
        endpoint = azure_devops.ENDPOINTS[command]
        assert endpoint[0] == host
        assert endpoint[2] == version
        assert endpoint[3] == token_type
        assert endpoint[2] != "7.2"


def test_continuation_token_request_types() -> None:
    int_commands = [("projects", ()), ("deployments", ("--project", "p"))]
    string_commands = [("pipelines", ("--project", "p")),
                       ("builds", ("--project", "p")),
                       ("releasedefs", ("--project", "p")),
                       ("environments", ("--project", "p"))]
    for command, extra in int_commands:
        args = (command, *extra, "--continuationToken", "7")
        assert isinstance(_args(*args).continuationToken, int)
    for command, extra in string_commands:
        args = (command, *extra, "--continuationToken", "7")
        assert isinstance(_args(*args).continuationToken, str)


def test_release_hosts_and_capital_r_path() -> None:
    host, url, _params, _body, method = _url(
        "release-env", "--project", "p", "--releaseId", "1",
        "--environmentId", "2",
    )
    assert host == "vsrm.dev.azure.com"
    assert "/_apis/Release/releases/1/environments/2?" in url
    assert method == "GET"


def test_environments_and_k8s_use_7_1_preview_1() -> None:
    _host, _url_text, env_params, _body, _method = _url(
        "environments", "--project", "p",
    )
    _host, _url_text, k8s_params, _body, _method = _url(
        "k8s", "--project", "p", "--envId", "3", "--resourceId", "4",
    )
    assert env_params["api-version"] == "7.1-preview.1"
    assert k8s_params["api-version"] == "7.1-preview.1"


def test_release_env_uses_7_1_preview_7() -> None:
    _host, _url_text, params, _body, _method = _url(
        "release-env", "--project", "p", "--releaseId", "1", "--environmentId", "2",
    )
    assert params["api-version"] == "7.1-preview.7"


def test_api_version_flag_overrides_endpoint_default() -> None:
    args = _args("--api-version", "7.9-test", "projects")
    _host, _url_text, params, _body, _method = azure_devops._request_parts(args, "org")
    assert params["api-version"] == "7.9-test"


def test_wiql_team_slash_before_apis() -> None:
    _host, url, _params, _body, _method = _url(
        "wiql", "--project", "p", "--team", "myteam", "--query", "Select [System.Id]",
    )
    assert "/p/myteam/_apis/wit/wiql?" in url
    assert "myteam_apis" not in url


def test_pat_basic_auth_uses_empty_username() -> None:
    old_pat = os.environ.get("AZURE_DEVOPS_PAT")
    old_bearer = os.environ.get("AZURE_DEVOPS_BEARER_TOKEN")
    os.environ["AZURE_DEVOPS_PAT"] = "pat"
    os.environ.pop("AZURE_DEVOPS_BEARER_TOKEN", None)
    try:
        encoded = base64.b64encode(b":pat").decode("ascii")
        assert azure_devops._auth_header() == f"Basic {encoded}"
    finally:
        if old_pat is None:
            os.environ.pop("AZURE_DEVOPS_PAT", None)
        else:
            os.environ["AZURE_DEVOPS_PAT"] = old_pat
        if old_bearer is None:
            os.environ.pop("AZURE_DEVOPS_BEARER_TOKEN", None)
        else:
            os.environ["AZURE_DEVOPS_BEARER_TOKEN"] = old_bearer


def test_build_projection_includes_repository_and_source_version() -> None:
    payload = {"count": 1, "value": [{"id": 7, "buildNumber": "b",
        "status": "completed", "result": "succeeded",
        "repository": {"id": "r1", "name": "repo", "type": "TfsGit",
                       "url": "https://example", "defaultBranch": "main"},
        "sourceVersion": "abc"}]}
    assert azure_devops._build_rows(payload) == [
        (7, "b", "completed", "succeeded", "r1", "repo", "TfsGit",
         "https://example", "main", "abc")
    ]


def test_build_projection_survives_null_repository() -> None:
    payload = {"count": 1, "value": [{"id": 8, "buildNumber": "b2",
        "status": "completed", "result": "succeeded",
        "repository": None, "sourceVersion": "def"}]}
    assert azure_devops._build_rows(payload) == [
        (8, "b2", "completed", "succeeded", None, None, None, None, None, "def")
    ]


def test_run_rows_drops_repo_columns() -> None:
    payload = {"count": 1, "value": [{"id": 1, "name": "run1", "state": "completed",
        "result": "succeeded"}]}
    assert azure_devops._run_rows(payload) == [(1, "run1", "completed", "succeeded")]


def test_deployment_projection_uses_real_fields() -> None:
    payload = {"count": 1, "value": [{"id": 5, "deploymentStatus": "succeeded",
        "operationStatus": "queued",
        "release": {"id": 10, "name": "rel1"},
        "releaseEnvironment": {"id": 20, "name": "prod"}}]}
    assert azure_devops._deployment_rows(payload) == [
        (5, "succeeded", "queued", 10, "rel1", 20, "prod")
    ]


def test_item_rows_handles_single_object_shape() -> None:
    payload = {"path": "/README.md", "objectId": "abc123", "commitId": "def456",
               "gitObjectType": "blob", "isFolder": False}
    assert azure_devops._item_rows(payload) == [
        ("/README.md", "abc123", "def456", "blob", False)
    ]


def test_release_env_rows_handles_single_object_shape() -> None:
    payload = {"id": 42, "name": "prod-env", "status": "succeeded"}
    assert azure_devops._release_env_rows(payload) == [(42, "prod-env", "succeeded")]


def test_non_json_response_exits_without_raising() -> None:
    old_urlopen = azure_devops.urllib.request.urlopen

    class _FakeResponse:
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def read(self) -> bytes:
            return b"not json, e.g. a zip payload"

        headers: dict[str, str] = {}

    def fake_urlopen(_request: object, timeout: int) -> object:
        del timeout
        return _FakeResponse()

    azure_devops.urllib.request.urlopen = fake_urlopen
    try:
        try:
            azure_devops._fetch(
                "https://dev.azure.com/org/p/_apis/git/repositories/r/items",
                "GET", None, "Bearer token",
            )
        except SystemExit as err:
            assert "not JSON" in str(err)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        azure_devops.urllib.request.urlopen = old_urlopen


def test_k8s_projection_includes_cluster_and_namespace() -> None:
    payload = {"clusterName": "aks", "namespace": "prod",
               "serviceEndpointId": "svc", "tags": ["a"],
               "environmentReference": {"id": 1}}
    assert azure_devops._k8s_rows(payload) == [
        ("aks", "prod", "svc", ["a"], {"id": 1})
    ]


def test_releasedefs_projection_includes_artifact_source_id() -> None:
    payload = {"count": 1, "value": [{"id": 1, "name": "rel",
        "artifactSourceId": "guid:42", "artifactType": "Build"}]}
    assert azure_devops._releasedef_rows(payload) == [
        (1, "rel", "guid:42", "Build")
    ]


def test_wiql_posts_body_and_reads_work_item_ids() -> None:
    _host, url, params, body, method = _url(
        "wiql", "--project", "p", "--query", "Select [System.Id]",
    )
    assert method == "POST"
    assert params["api-version"] == "7.2-preview.2"
    assert json.loads(body.decode("utf-8")) == {
        "query": "Select [System.Id]",
    }
    assert "/_apis/wit/wiql?" in url
    payload = {"queryType": "flat", "asOf": "now", "columns": [],
               "sortColumns": [], "workItems": [{"id": 123, "url": "u"}]}
    assert azure_devops._wiql_rows(payload) == [(123, "u")]


def test_missing_pat_exits_without_bearer() -> None:
    old_pat = os.environ.get("AZURE_DEVOPS_PAT")
    old_bearer = os.environ.get("AZURE_DEVOPS_BEARER_TOKEN")
    os.environ.pop("AZURE_DEVOPS_PAT", None)
    os.environ.pop("AZURE_DEVOPS_BEARER_TOKEN", None)
    try:
        try:
            azure_devops._auth_header()
        except SystemExit as err:
            assert "AZURE_DEVOPS_PAT" in str(err)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        if old_pat is not None:
            os.environ["AZURE_DEVOPS_PAT"] = old_pat
        if old_bearer is not None:
            os.environ["AZURE_DEVOPS_BEARER_TOKEN"] = old_bearer


def test_http_error_does_not_echo_raw_body() -> None:
    text = _stderr_from_error(b"proxy echoed Authorization: Bearer secret")
    assert text.strip() == "HTTP 403 Forbidden"
    assert "Authorization" not in text
    text = _stderr_from_error(
        json.dumps({"message": "vendor message"}).encode()
    )
    assert "vendor message" in text


if __name__ == "__main__":
    test_endpoint_table_versions_hosts_and_continuation_types()
    test_continuation_token_request_types()
    test_release_hosts_and_capital_r_path()
    test_environments_and_k8s_use_7_1_preview_1()
    test_release_env_uses_7_1_preview_7()
    test_api_version_flag_overrides_endpoint_default()
    test_wiql_team_slash_before_apis()
    test_pat_basic_auth_uses_empty_username()
    test_build_projection_includes_repository_and_source_version()
    test_build_projection_survives_null_repository()
    test_run_rows_drops_repo_columns()
    test_deployment_projection_uses_real_fields()
    test_item_rows_handles_single_object_shape()
    test_release_env_rows_handles_single_object_shape()
    test_non_json_response_exits_without_raising()
    test_k8s_projection_includes_cluster_and_namespace()
    test_releasedefs_projection_includes_artifact_source_id()
    test_wiql_posts_body_and_reads_work_item_ids()
    test_missing_pat_exits_without_bearer()
    test_http_error_does_not_echo_raw_body()
    print("ok")
