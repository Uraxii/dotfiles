#!/usr/bin/env python3
"""Read-only Azure DevOps query CLI.

Env: AZURE_DEVOPS_ORG plus AZURE_DEVOPS_PAT or AZURE_DEVOPS_BEARER_TOKEN.
Example:
    azure_devops.py builds --project PROJECT
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

TIMEOUT_SEC = 30
MAX_ERROR_MESSAGE_CHARS = 200

ENDPOINTS = {
    "projects": ("dev.azure.com", "/{org}/_apis/projects", "7.2-preview.4", "int32"),
    "repos": ("dev.azure.com",
              "/{org}/{project}/_apis/git/repositories",
              "7.2-preview.2", None),
    "items": ("dev.azure.com",
              "/{org}/{project}/_apis/git/repositories/{repoId}/items",
              "7.2-preview.1", None),
    "pipelines": ("dev.azure.com", "/{org}/{project}/_apis/pipelines",
                  "7.2-preview.1", "string"),
    "runs": ("dev.azure.com", "/{org}/{project}/_apis/pipelines/{pipelineId}/runs",
             "7.2-preview.1", None),
    "builds": ("dev.azure.com", "/{org}/{project}/_apis/build/builds",
               "7.2-preview.8", "string"),
    "artifacts": ("dev.azure.com",
                  "/{org}/{project}/_apis/build/builds/{buildId}/artifacts",
                  "7.2-preview.5", None),
    "deployments": ("vsrm.dev.azure.com", "/{org}/{project}/_apis/release/deployments",
                    "7.2-preview.2", "int32"),
    "releasedefs": ("vsrm.dev.azure.com", "/{org}/{project}/_apis/release/definitions",
                    "7.2-preview.4", "string"),
    "release-env": ("vsrm.dev.azure.com",
                    "/{org}/{project}/_apis/Release/releases/{releaseId}"
                    "/environments/{environmentId}",
                    "7.1-preview.7", None),
    "environments": ("dev.azure.com", "/{org}/{project}/_apis/distributedtask/environments",
                     "7.1-preview.1", "string"),
    "k8s": ("dev.azure.com",
            "/{org}/{project}/_apis/distributedtask/environments/{envId}"
            "/providers/kubernetes/{resourceId}",
            "7.1-preview.1", None),
    "wiql": ("dev.azure.com", "/{org}/{project}/{team}_apis/wit/wiql",
             "7.2-preview.2", None),
}

__all__ = ["ENDPOINTS", "build_parser", "main"]

def _org(cli_org: str | None) -> str:
    org = cli_org or os.environ.get("AZURE_DEVOPS_ORG")
    if not org:
        sys.exit("missing AZURE_DEVOPS_ORG")
    return org

def _auth_header() -> str:
    bearer = os.environ.get("AZURE_DEVOPS_BEARER_TOKEN")
    if bearer:
        return f"Bearer {bearer}"
    pat = os.environ.get("AZURE_DEVOPS_PAT")
    if not pat:
        sys.exit("missing AZURE_DEVOPS_PAT or AZURE_DEVOPS_BEARER_TOKEN")
    encoded = base64.b64encode(f":{pat}".encode("ascii")).decode("ascii")
    return f"Basic {encoded}"

def _path_value(value: object) -> str:
    return urllib.parse.quote(str(value), safe="")

def _request_parts(
    args: argparse.Namespace, org: str
) -> tuple[str, str, dict[str, object], bytes | None, str]:
    host, template, version, _token_type = ENDPOINTS[args.command]
    values = vars(args) | {"org": org}
    if args.command == "wiql":
        # Team segment is optional in the real path: "{team}/_apis/..." when
        # given, "_apis/..." (no team) when not. Pre-quote it here (with its
        # own trailing slash) so the generic quoting below leaves it alone.
        team = values.get("team") or ""
        values["team"] = f"{_path_value(team)}/" if team else ""
    path = template.format_map({key: value if key == "team" else _path_value(value)
                                for key, value in values.items()
                                if value is not None})
    version = getattr(args, "api_version", None) or version
    params = _params(args, version)
    body = None
    method = "GET"
    if args.command == "wiql":
        body = json.dumps({"query": args.query}).encode("utf-8")
        method = "POST"
    query = urllib.parse.urlencode(params)
    return host, f"https://{host}{path}?{query}", params, body, method

def _params(args: argparse.Namespace, version: str) -> dict[str, object]:
    params: dict[str, object] = {"api-version": version}
    for name in (
        "continuationToken", "stateFilter", "includeLinks", "includeAllUrls",
        "includeHidden", "path", "includeContent", "format", "orderBy",
        "definitions", "repositoryId", "repositoryType", "branchName",
        "minTime", "maxTime", "statusFilter", "resultFilter", "queryOrder",
        "buildIds", "tagFilters", "definitionId", "deploymentStatus",
        "operationStatus", "sourceBranch", "latestAttemptsOnly",
        "minStartedTime", "maxStartedTime", "expand", "artifactType",
        "artifactSourceId", "name",
    ):
        value = getattr(args, name, None)
        if value is not None:
            params[_api_name(name)] = value
    if getattr(args, "limit", None) is not None and args.command != "repos":
        params["$top"] = args.limit
    if getattr(args, "skip", None) is not None:
        params["$skip"] = args.skip
    return params

def _api_name(name: str) -> str:
    return {"format": "$format", "expand": "$expand"}.get(name, name)

def _error_message(body: bytes) -> str | None:
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    text = payload.get("message") or payload.get("typeKey")
    return text[:MAX_ERROR_MESSAGE_CHARS] if isinstance(text, str) and text else None

def _fetch(
    url: str, method: str, body: bytes | None, auth: str
) -> tuple[dict, str | None]:
    headers = {"Authorization": auth, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read()
            token = resp.headers.get("x-ms-continuationtoken")
        try:
            return json.loads(raw), token
        except json.JSONDecodeError:
            sys.exit("response was not JSON (e.g. --format text/zip); "
                     "this tool only handles JSON responses")
    except urllib.error.HTTPError as err:
        status = f"HTTP {err.code} {err.reason}"
        message = _error_message(err.read())
        print(f"{status}\n{message}" if message else status, file=sys.stderr)
        sys.exit(1)

def _field(value: object) -> str:
    if value is None or value == "":
        return "-"
    text = str(value)
    return text if len(text) <= 80 else text[:77] + "..."

def _print(header: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    print("\t".join(header))
    for row in rows:
        print("\t".join(_field(value) for value in row))

def _records(payload: dict) -> list[dict]:
    data = payload.get("value", [])
    return data if isinstance(data, list) else []

def _project_rows(payload: dict) -> list[tuple[object, ...]]:
    return [(item.get("id"), item.get("name"), item.get("state"),
             item.get("visibility"), item.get("description"))
            for item in _records(payload)]

def _repo_rows(payload: dict, limit: int) -> list[tuple[object, ...]]:
    return [(item.get("id"), item.get("name"), item.get("defaultBranch"),
             item.get("size"), item.get("isDisabled"))
            for item in _records(payload)[:limit]]

def _build_rows(payload: dict) -> list[tuple[object, ...]]:
    rows = []
    for item in _records(payload):
        repo = item.get("repository") or {}  # null on deleted/xaml/no-repo builds
        rows.append((item.get("id"), item.get("buildNumber"), item.get("status"),
                     item.get("result"), repo.get("id"), repo.get("name"),
                     repo.get("type"), repo.get("url"), repo.get("defaultBranch"),
                     item.get("sourceVersion")))
    return rows


def _run_rows(payload: dict) -> list[tuple[object, ...]]:
    # The runs LIST response never includes "resources" (only run-detail
    # does), so repo refs/versions can never populate here. Dropped rather
    # than faked; see SKILL.md.
    return [(item.get("id"), item.get("name"), item.get("state"),
             item.get("result"))
            for item in _records(payload)]


def _deployment_rows(payload: dict) -> list[tuple[object, ...]]:
    rows = []
    for item in _records(payload):
        release = item.get("release") or {}
        env = item.get("releaseEnvironment") or {}
        rows.append((item.get("id"), item.get("deploymentStatus"),
                     item.get("operationStatus"), release.get("id"),
                     release.get("name"), env.get("id"), env.get("name")))
    return rows


def _artifact_rows(payload: dict) -> list[tuple[object, ...]]:
    rows = []
    for item in _records(payload):
        resource = item.get("resource") or {}
        rows.append((item.get("id"), item.get("name"), item.get("source"),
                     resource.get("type"), resource.get("downloadUrl")))
    return rows


def _item_rows(payload: dict) -> list[tuple[object, ...]]:
    items = _records(payload) or [payload]  # single-object shape, not {"value": [...]}
    return [(item.get("path"), item.get("objectId"), item.get("commitId"),
             item.get("gitObjectType"), item.get("isFolder"))
            for item in items]


def _release_env_rows(payload: dict) -> list[tuple[object, ...]]:
    items = _records(payload) or [payload]  # single-object shape, not {"value": [...]}
    return [(item.get("id"), item.get("name"), item.get("status"))
            for item in items]


def _pipeline_rows(payload: dict) -> list[tuple[object, ...]]:
    return [(item.get("id"), item.get("name"), item.get("folder"),
             item.get("revision"))
            for item in _records(payload)]


def _releasedef_rows(payload: dict) -> list[tuple[object, ...]]:
    return [(item.get("id"), item.get("name"), item.get("artifactSourceId"),
             item.get("artifactType"))
            for item in _records(payload)]


def _k8s_rows(payload: dict) -> list[tuple[object, ...]]:
    items = _records(payload) or [payload]
    return [(item.get("clusterName"), item.get("namespace"),
             item.get("serviceEndpointId"), item.get("tags"),
             item.get("environmentReference"))
            for item in items]


def _wiql_rows(payload: dict) -> list[tuple[object, ...]]:
    return [(item.get("id"), item.get("url")) for item in payload.get("workItems", [])]


def _generic_rows(payload: dict) -> list[tuple[object, ...]]:
    return [(item.get("id"), item.get("name"), item.get("state")) for item in _records(payload)]


ROWS: dict[str, tuple[tuple[str, ...], Callable[..., list[tuple[object, ...]]]]] = {
    "projects": (("id", "name", "state", "visibility", "description"),
                 _project_rows),
    "repos": (("id", "name", "default_branch", "size", "disabled"),
              _repo_rows),
    "builds": (("id", "number", "status", "result", "repo_id",
                "repo_name", "repo_type", "repo_url", "default_branch",
                "source_version"), _build_rows),
    "runs": (("id", "name", "state", "result"), _run_rows),
    "releasedefs": (("id", "name", "artifact_source_id", "artifact_type"),
                    _releasedef_rows),
    "k8s": (("cluster_name", "namespace", "service_endpoint_id", "tags",
             "environment_reference"), _k8s_rows),
    "wiql": (("id", "url"), _wiql_rows),
    "deployments": (("id", "deployment_status", "operation_status", "release_id",
                     "release_name", "environment_id", "environment_name"),
                    _deployment_rows),
    "artifacts": (("id", "name", "source", "resource_type", "download_url"),
                  _artifact_rows),
    "items": (("path", "object_id", "commit_id", "object_type", "is_folder"),
              _item_rows),
    "release-env": (("id", "name", "status"), _release_env_rows),
    "pipelines": (("id", "name", "folder", "revision"), _pipeline_rows),
}

def _show_next(token: str | None) -> None:
    if token:
        print(f"continuationToken: {token}", file=sys.stderr)


def _add_common(parser: argparse.ArgumentParser, token_type: str = "string") -> None:
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--continuationToken", type=int if token_type == "int32" else str,
                        default=None)
    parser.add_argument("--raw", action="store_true")


def _add_project_raw(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", required=True)
    parser.add_argument("--raw", action="store_true")


def _add_project_common(parser: argparse.ArgumentParser, token_type: str = "string") -> None:
    parser.add_argument("--project", required=True)
    _add_common(parser, token_type)


def _add_string_args(parser: argparse.ArgumentParser, names: tuple[str, ...]) -> None:
    for name in names:
        parser.add_argument(f"--{name}", default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", default=None,
                        help="Azure DevOps organization; overrides env")
    parser.add_argument("--api-version", default=None,
                        help="override the endpoint's default api-version string")
    sub = parser.add_subparsers(dest="command", required=True)

    projects = sub.add_parser("projects")
    _add_common(projects, "int32")
    projects.add_argument("--skip", type=int, default=None)
    projects.add_argument("--stateFilter", default=None)

    repos = sub.add_parser("repos", help="limit is applied client-side")
    repos.add_argument("--project", required=True)
    repos.add_argument("--limit", type=int, default=20)
    repos.add_argument("--includeLinks", action="store_true", default=None)
    repos.add_argument("--includeAllUrls", action="store_true", default=None)
    repos.add_argument("--includeHidden", action="store_true", default=None)
    repos.add_argument("--raw", action="store_true")

    items = sub.add_parser("items")
    _add_project_raw(items)
    items.add_argument("--repoId", required=True)
    items.add_argument("--path", default=None)
    items.add_argument("--includeContent", action="store_true", default=None)
    items.add_argument("--format", default=None)

    pipelines = sub.add_parser("pipelines")
    _add_project_common(pipelines)
    pipelines.add_argument("--orderBy", default=None)

    runs = sub.add_parser("runs",
                          help="top 10000 returned by API; no paging params")
    _add_project_raw(runs)
    runs.add_argument("--pipelineId", required=True)

    builds = sub.add_parser("builds")
    _add_project_common(builds)
    _add_string_args(builds, ("definitions", "repositoryId", "repositoryType",
                              "branchName", "minTime", "maxTime",
                              "statusFilter", "resultFilter", "queryOrder",
                              "buildIds", "tagFilters"))

    artifacts = sub.add_parser("artifacts")
    _add_project_raw(artifacts)
    artifacts.add_argument("--buildId", required=True)

    deployments = sub.add_parser("deployments")
    _add_project_common(deployments, "int32")
    _add_string_args(deployments, ("definitionId", "deploymentStatus",
                                   "operationStatus", "sourceBranch",
                                   "latestAttemptsOnly", "queryOrder",
                                   "minStartedTime", "maxStartedTime"))

    releasedefs = sub.add_parser("releasedefs")
    _add_project_common(releasedefs)
    releasedefs.add_argument("--expand", default=None,
                             help="environments|artifacts|triggers|variables|"
                                  "tags|lastRelease")
    releasedefs.add_argument("--artifactType", default=None)
    releasedefs.add_argument("--artifactSourceId", default=None,
                             help="{projectGuid}:{BuildDefinitionId}")

    release_env = sub.add_parser("release-env")
    _add_project_raw(release_env)
    release_env.add_argument("--releaseId", required=True)
    release_env.add_argument("--environmentId", required=True)

    environments = sub.add_parser("environments")
    _add_project_common(environments)
    environments.add_argument("--name", default=None)

    k8s = sub.add_parser("k8s")
    _add_project_raw(k8s)
    k8s.add_argument("--envId", required=True)
    k8s.add_argument("--resourceId", required=True)

    wiql = sub.add_parser("wiql",
                          help="POSTs read-only WIQL; returns work item ids "
                               "only, not hydrated workitems")
    wiql.add_argument("--project", required=True)
    wiql.add_argument("--team", default="")
    wiql.add_argument("--query", required=True)
    wiql.add_argument("--raw", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _host, url, _params_out, body, method = _request_parts(args, _org(args.org))
    payload, next_token = _fetch(url, method, body, _auth_header())
    if args.raw:
        print(json.dumps(payload, separators=(",", ":")))
    else:
        header, row_func = ROWS.get(args.command, (("id", "name", "state"),
                                                   _generic_rows))
        rows = row_func(payload, args.limit) if args.command == "repos" else (
            row_func(payload))
        _print(header, rows)
    _show_next(next_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
