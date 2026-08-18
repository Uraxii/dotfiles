#!/usr/bin/env python3
"""Read-only OX Security GraphQL query CLI.

Env: OX_API_KEY, optional OX_API_URL and OX_AUTH_BEARER=1. Example:
    ox_security.py issues --search CVE-2026
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence

API = "https://api.cloud.ox.security/api/apollo-gateway"
TIMEOUT_SEC = 30
DEFAULT_LIMIT = 20
MAX_ERROR_MESSAGE_CHARS = 200
ALLOWED_OPERATIONS = frozenset({"GetIssues", "GetApplications"})
ISSUES_QUERY = """
query GetIssues($getIssuesInput: IssuesInput) {
  # IssuesInput.limit is Int! in OX's schema; _issue_input always sends it.
  getIssues(getIssuesInput: $getIssuesInput) {
    totalIssues
    totalFilteredIssues
    issues {
      issueId
      sourceTools
      connector
      originalToolSeverity
      issueStatus
      name
      appName
      isFixAvailable
      isFixApplied
      app { repoName branch businessPriority }
      scaVulnerabilities { cve epss percentile exploitInTheWild }
      # Vendor spelling is prDeatils in OX's schema.
      prDeatils { prURL prStatus }
    }
  }
}
"""
APPLICATION_FIELDS = """
      appId
      repoName
      organization
      branch
      headSha
      deployedProd
      businessPriority
      matchedProjects {
        toolName
        matchedProjects { externalToolProject matchMethod }
      }
      applicationFlows {
        repository { type system date location { runBy foundBy foundIn link } }
        cicdInfo {
          type
          system
          latestDate
          lastMonthJobCount
          location { runBy foundBy foundIn link }
        }
        artifacts { hash cluster region k8sType location { runBy foundBy foundIn link } }
        kubernetes { name location { runBy foundBy foundIn link } }
        cloudDeployments { imageName k8sType cluster region hash link }
      }
"""
APPLICATIONS_QUERY = f"""
query GetApplications($getApplicationsInput: GetApplicationsInput) {{
  # GetApplicationsInput.limit is Int in OX's schema.
  getApplications(getApplicationsInput: $getApplicationsInput) {{
    applications {{
{APPLICATION_FIELDS}
    }}
    total
    totalFilteredApps
  }}
}}
"""
__all__ = ["ALLOWED_OPERATIONS", "APPLICATIONS_QUERY", "ISSUES_QUERY", "main"]


def _token() -> str:
    token = os.environ.get("OX_API_KEY")
    if not token:
        raise SystemExit("missing OX_API_KEY")
    return token


def _headers(token: str) -> dict[str, str]:
    auth = f"Bearer {token}" if os.environ.get("OX_AUTH_BEARER") else token
    return {
        "Authorization": auth,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _error_message(body: bytes) -> str | None:
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if not isinstance(errors, list):
        return None
    messages = []
    for error in errors:
        text = error.get("message") if isinstance(error, dict) else None
        if isinstance(text, str) and text:
            messages.append(text[:MAX_ERROR_MESSAGE_CHARS])
    return "; ".join(messages) if messages else None


def _post(
    operation_name: str,
    query: str,
    variables: Mapping[str, object],
) -> dict[str, object]:
    if operation_name not in ALLOWED_OPERATIONS:
        raise SystemExit(f"refusing non-read-only OX operation: {operation_name}")
    if not query.lstrip().lower().startswith("query "):
        raise SystemExit(f"refusing non-query document: {operation_name}")
    body = json.dumps({
        "operationName": operation_name,
        "query": query,
        "variables": variables,
    }).encode("utf-8")
    request = urllib.request.Request(
        os.environ.get("OX_API_URL", API),
        data=body,
        headers=_headers(_token()),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:
            try:
                payload = json.load(response)
            except json.JSONDecodeError:
                sys.exit(
                    f"non-JSON response from "
                    f"{urllib.parse.urlparse(request.full_url).hostname}"
                )
    except urllib.error.HTTPError as error:
        status = f"HTTP {error.code} {error.reason}"
        message = _error_message(error.read())
        print(f"{status}\n{message}" if message else status, file=sys.stderr)
        raise SystemExit(1) from error
    _raise_graphql_errors(payload)
    return payload


def _raise_graphql_errors(payload: Mapping[str, object]) -> None:
    errors = payload.get("errors")
    if errors:
        print(json.dumps(errors, separators=(",", ":")), file=sys.stderr)
        raise SystemExit(1)


def _autocomplete(field_name: str, value: str | None) -> dict[str, object] | None:
    if not value:
        return None
    return {"fieldName": field_name, "value": [value]}


def _filter_search(values: Sequence[str] | None) -> list[dict[str, object]] | None:
    if not values:
        return None
    filters = []
    for item in values:
        field_name, sep, value = item.partition("=")
        if not sep:
            raise SystemExit("--filterSearch must be FIELD=VALUE")
        filters.append({"fieldName": field_name, "value": [value]})
    return filters


def _field(value: object) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ",".join(str(item) for item in value) or "-"
    text = str(value)
    return text if len(text) <= 80 else text[:77] + "..."


def _print_table(header: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
    print("\t".join(header))
    for row in rows:
        print("\t".join(_field(value) for value in row))


def _issue_records(payload: Mapping[str, object]) -> list[dict[str, object]]:
    data = payload.get("data", {})
    issues = data.get("getIssues", {}).get("issues", []) if isinstance(data, dict) else []
    return issues if isinstance(issues, list) else []


def _application_records(payload: Mapping[str, object]) -> list[dict[str, object]]:
    data = payload.get("data", {})
    apps = data.get("getApplications", {}) if isinstance(data, dict) else {}
    records = apps.get("applications", []) if isinstance(apps, dict) else []
    return records if isinstance(records, list) else []


def _first_sca(item: Mapping[str, object]) -> Mapping[str, object]:
    vulnerabilities = item.get("scaVulnerabilities")
    if isinstance(vulnerabilities, list) and vulnerabilities:
        first = vulnerabilities[0]
        return first if isinstance(first, dict) else {}
    return {}


def _issue_rows(payload: Mapping[str, object]) -> list[tuple[object, ...]]:
    rows = []
    for item in _issue_records(payload):
        app = item.get("app") if isinstance(item.get("app"), dict) else {}
        sca = _first_sca(item)
        rows.append((
            item.get("appName"),
            app.get("businessPriority"),
            item.get("originalToolSeverity"),
            item.get("sourceTools"),
            sca.get("epss"),
            sca.get("percentile"),
            sca.get("exploitInTheWild"),
            item.get("isFixAvailable"),
        ))
    return rows


def _names(items: object, keys: Sequence[str]) -> str:
    if not isinstance(items, list):
        return "-"
    values = []
    for item in items:
        if isinstance(item, dict):
            values.append(next((str(item[key]) for key in keys if item.get(key)), ""))
    return ",".join(value for value in values if value) or "-"


def _app_rows(payload: Mapping[str, object]) -> list[tuple[object, ...]]:
    return [
        (
            item.get("appId") or item.get("repoName"),
            item.get("repoName"),
            item.get("branch"),
            item.get("deployedProd"),
            item.get("businessPriority"),
            _names(item.get("matchedProjects"), ("toolName",)),
        )
        for item in _application_records(payload)
    ]


def _flow_rows(payload: Mapping[str, object]) -> list[tuple[object, ...]]:
    rows = []
    for app in _application_records(payload):
        flows = app.get("applicationFlows")
        flow = flows[0] if isinstance(flows, list) and flows else flows
        flow = flow if isinstance(flow, dict) else {}
        rows.append((
            app.get("repoName"),
            app.get("branch"),
            app.get("deployedProd"),
            _names(flow.get("repository"), ("system", "type", "date")),
            _names(
                flow.get("cicdInfo"),
                ("system", "type", "latestDate", "lastMonthJobCount"),
            ),
            _names(flow.get("artifacts"), ("hash",)),
            _names(flow.get("kubernetes"), ("name",)),
            _names(flow.get("cloudDeployments"), ("imageName", "cluster", "region")),
        ))
    return rows


def _issue_input(args: argparse.Namespace) -> dict[str, object]:
    data: dict[str, object] = {"limit": args.limit}
    for key in ("page", "offset", "cursorValue"):
        value = getattr(args, key, None)
        if value is not None:
            data[key] = value
    searches = [
        item for item in (
            _autocomplete("severity", args.severity),
            _autocomplete("app", args.app),
        ) if item
    ]
    if searches:
        data["search"] = searches
    if args.search:
        data["topLevelSearch"] = args.search
    return data


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--search", default=None)
    parser.add_argument("--page", type=int, default=None)
    parser.add_argument("--offset", type=int, default=None)
    parser.add_argument("--raw", action="store_true")


def _app_input(args: argparse.Namespace) -> dict[str, object]:
    data: dict[str, object] = {"limit": args.limit}
    for key in ("page", "offset"):
        value = getattr(args, key, None)
        if value is not None:
            data[key] = value
    filters = _filter_search(getattr(args, "filterSearch", None))
    if filters:
        data["filterSearch"] = filters
    if args.search:
        data["search"] = args.search
    app_id = getattr(args, "appId", None)
    if app_id:
        data["appId"] = app_id
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    issues = sub.add_parser("issues")
    _add_common(issues)
    issues.add_argument("--severity", default=None)
    issues.add_argument("--app", default=None)
    issues.add_argument("--cursorValue", default=None)
    apps = sub.add_parser("apps")
    _add_common(apps)
    apps.add_argument("--filterSearch", action="append", default=None)
    flows = sub.add_parser("app-flows")
    flows.add_argument("appId")
    flows.add_argument("--raw", action="store_true")
    return parser


def _show(payload: Mapping[str, object], args: argparse.Namespace) -> None:
    if args.raw:
        print(json.dumps(payload, separators=(",", ":")))
    elif args.command == "issues":
        header = ("app", "priority", "severity", "tools",
                  "epss", "pct", "wild", "fix")
        _print_table(header, _issue_rows(payload))
    elif args.command == "apps":
        _print_table(("appId", "repo", "branch", "prod", "priority", "matched"),
                     _app_rows(payload))
    else:
        header = ("repo", "branch", "prod", "repository", "cicd",
                  "artifact", "k8s", "cloud")
        _print_table(header, _flow_rows(payload))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "issues":
        variables = {"getIssuesInput": _issue_input(args)}
        payload = _post("GetIssues", ISSUES_QUERY, variables)
    elif args.command == "apps":
        variables = {"getApplicationsInput": _app_input(args)}
        payload = _post("GetApplications", APPLICATIONS_QUERY, variables)
    else:
        variables = {"getApplicationsInput": {"limit": 1, "appId": args.appId}}
        payload = _post("GetApplications", APPLICATIONS_QUERY, variables)
    _show(payload, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
