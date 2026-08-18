#!/usr/bin/env python3
"""Read-only Sysdig Secure query CLI."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_SEC = 30
DEFAULT_LIMIT = 20
MAX_ERROR_MESSAGE_CHARS = 200
RUNTIME_MAX_LIMIT = 1000
REGISTRY_MAX_LIMIT = 1000
REGIONS = "us1 us2 us3 us4 eu1 eu2 au1 me2 in1 jp1"
__all__ = ["build_parser", "main"]


def _token() -> str:
    token = os.environ.get("SYSDIG_API_TOKEN")
    if not token:
        sys.exit("missing SYSDIG_API_TOKEN")
    return token


def _host(cli_host: str | None, path: str) -> str:
    raw = cli_host or os.environ.get("SYSDIG_HOST")
    if not raw:
        sys.exit(
            "missing SYSDIG_HOST; valid regions: "
            f"{REGIONS}; patterns https://api.<region>.sysdig.com, app hosts"
        )
    if raw.startswith("https://"):
        return raw.rstrip("/")
    if path.startswith("/secure/"):
        return f"https://api.{raw}.sysdig.com"
    if raw == "us1":
        return "https://secure.sysdig.com"
    if raw in ("us2", "eu1"):
        return f"https://{raw}.app.sysdig.com"
    return f"https://app.{raw}.sysdig.com"


def _limit(value: int, max_value: int) -> int:
    return min(max(value, 1), max_value)


def _url(host: str, path: str, params: dict[str, object]) -> str:
    clean = {key: value for key, value in params.items() if value is not None}
    query = urllib.parse.urlencode(clean)
    return f"{host}{path}?{query}" if query else f"{host}{path}"


def _error_message(body: bytes) -> str | None:
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    text = payload.get("message") or payload.get("error")
    return text[:MAX_ERROR_MESSAGE_CHARS] if isinstance(text, str) and text else None


def _get(path: str, params: dict[str, object], token: str, host: str) -> dict:
    req = urllib.request.Request(
        _url(host, path, params),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            try:
                return json.load(resp)
            except json.JSONDecodeError:
                sys.exit(f"non-JSON response from {urllib.parse.urlparse(host).hostname}")
    except urllib.error.HTTPError as err:
        status = f"HTTP {err.code} {err.reason}"
        message = _error_message(err.read())
        print(f"{status}\n{message}" if message else status, file=sys.stderr)
        sys.exit(1)


def _field(value: object) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, separators=(",", ":"), sort_keys=True)
    else:
        text = str(value)
    return text if len(text) <= 80 else text[:77] + "..."


def _print(header: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    print("\t".join(header))
    for row in rows:
        print("\t".join(_field(value) for value in row))


def _records(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return payload
    data = payload.get("data")
    if isinstance(data, list):
        return data
    zones = payload.get("zones", [])
    return zones if isinstance(zones, list) else []


def _severity(value: object) -> str:
    if not isinstance(value, dict):
        return "-"
    order = ("critical", "high", "medium", "low", "negligible")
    parts = [f"{name}:{value.get(name, 0)}" for name in order]
    return ",".join(parts)


def _scope(item: dict, key: str) -> object:
    scope = item.get("scope")
    if not isinstance(scope, dict):
        return None
    return scope.get(key)


def _runtime_rows(payload: dict | list) -> list[tuple[object, ...]]:
    return [
        (
            item.get("resultId"),
            item.get("mainAssetName"),
            _scope(item, "asset.type"),
            _scope(item, "kubernetes.cluster.name"),
            _scope(item, "kubernetes.namespace.name"),
            _severity(item.get("runningVulnTotalBySeverity")),
            _severity(item.get("vulnTotalBySeverity")),
            item.get("policyEvaluationResult"),
        )
        for item in _records(payload)
    ]


def _result_rows(payload: dict | list) -> list[tuple[object, ...]]:
    result = payload.get("result", payload) if isinstance(payload, dict) else {}
    packages = result.get("packages", {}) if isinstance(result, dict) else {}
    vulns = result.get("vulnerabilities", {}) if isinstance(result, dict) else {}
    rows = []
    if not isinstance(packages, dict) or not isinstance(vulns, dict):
        return rows
    for package in packages.values():
        refs = package.get("vulnerabilitiesRefs", [])
        for ref in refs:
            vuln = vulns.get(ref, {})
            rows.append(
                (
                    package.get("name"),
                    package.get("version"),
                    vuln.get("name"),
                    vuln.get("severity"),
                    vuln.get("exploitable"),
                    vuln.get("exploit"),
                    vuln.get("acceptedRisks"),
                    vuln.get("suggestedFix"),
                )
            )
    return rows


def _basic_rows(payload: dict | list) -> list[tuple[object, ...]]:
    return [
        (
            item.get("resultId") or item.get("id") or item.get("hash"),
            item.get("mainAssetName") or item.get("pullString") or item.get("name"),
            item.get("type") or item.get("assetType"),
            item.get("policyEvaluationResult") or item.get("passed"),
        )
        for item in _records(payload)
    ]


def _join_filter(existing: str | None, parts: list[str]) -> str | None:
    filters = []
    if existing:
        filters.append(existing)
    filters.extend(parts)
    return " and ".join(filters) if filters else None


def _filter_value(value: str) -> str:
    return value if value in ("true", "false") else json.dumps(value)


def _runtime_filter(args: argparse.Namespace) -> str | None:
    fields = (
        ("asset.type", args.asset_type),
        ("kubernetes.cluster.name", args.cluster),
        ("kubernetes.namespace.name", args.namespace),
        ("kubernetes.workload.name", args.workload),
        ("kubernetes.workload.type", args.workload_type),
        ("kubernetes.pod.container.name", args.container),
        ("agent.tag.env", args.env),
        ("policyStatus", args.policy_status),
        ("freeText", args.free_text),
    )
    parts = [f"{name}={_filter_value(value)}" for name, value in fields if value]
    if args.running:
        parts.append("hasRunningVulns=true")
    return _join_filter(args.filter, parts)


def _show_cursor(payload: dict | list) -> None:
    if isinstance(payload, dict) and isinstance(payload.get("page"), dict):
        next_cursor = payload["page"].get("next")
        if next_cursor:
            print(f"next cursor: {next_cursor}", file=sys.stderr)


def _show_cspm_page(payload: dict, page_number: int, page_size: int) -> None:
    del page_number, page_size
    page = payload.get("page")
    next_page = page.get("next") if isinstance(page, dict) else None
    if next_page:
        print(f"next pageNumber: {next_page}", file=sys.stderr)


def _zone_filter(value: str | None) -> str | None:
    if not value:
        return None
    return value if value.startswith("name:") else f"name:{value}"


def _show_offset(payload: dict | list, offset: int, limit: int) -> None:
    if len(_records(payload)) == limit:
        print(f"next offset: {offset + limit}", file=sys.stderr)


def _add_common(cmd: argparse.ArgumentParser,
                limit_default: int = DEFAULT_LIMIT) -> None:
    cmd.add_argument("--limit", type=int, default=limit_default)
    cmd.add_argument("--filter", default=None)
    cmd.add_argument("--raw", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=None,
                        help=f"Sysdig region or URL; regions: {REGIONS}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("runtime", "registry", "pipeline"):
        cmd = sub.add_parser(name)
        _add_common(cmd, 1000 if name == "registry" else DEFAULT_LIMIT)
        cmd.add_argument("--cursor", default=None)
    runtime = sub.choices["runtime"]
    for flag in (
        "--sort", "--asset-type", "--cluster", "--namespace", "--workload",
        "--workload-type", "--container", "--env", "--free-text",
    ):
        runtime.add_argument(flag, default=None)
    runtime.add_argument(
        "--policy-status",
        choices=("passed", "failed", "accepted", "noPolicy"),
        default=None,
    )
    runtime.add_argument("--running", action="store_true")
    result = sub.add_parser("result")
    result.add_argument("--id", required=True)
    result.add_argument("--raw", action="store_true")
    sboms = sub.add_parser("sboms")
    sboms.add_argument("--assetId", default=None)
    sboms.add_argument("--assetType", default=None)
    sboms.add_argument("--bomIdentifier", default=None)
    sboms.add_argument("--raw", action="store_true")
    inventory = sub.add_parser("inventory")
    inventory.add_argument("--filter", default=None)
    inventory.add_argument("--pageNumber", type=int, default=1)
    inventory.add_argument("--pageSize", type=int, default=50)
    inventory.add_argument("--fields", default=None)
    inventory.add_argument("--raw", action="store_true")
    zones = sub.add_parser("zones")
    _add_common(zones)
    zones.add_argument("--offset", type=int, default=0)
    zones.add_argument("--orderby", default=None)
    events = sub.add_parser("events")
    _add_common(events)
    events.add_argument("--from", dest="from_ns", required=True)
    events.add_argument("--to", dest="to_ns", required=True)
    events.add_argument("--cursor", default=None)
    return parser


def _emit(payload: dict, raw: bool, header: tuple[str, ...],
          rows: list[tuple[object, ...]]) -> None:
    if raw:
        print(json.dumps(payload, separators=(",", ":")))
        return
    _print(header, rows)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = _token()
    if args.command in ("runtime", "registry", "pipeline"):
        paths = {
            "runtime": "/secure/vulnerability/v1/runtime-results",
            "registry": "/secure/vulnerability/v1/registry-results",
            "pipeline": "/secure/vulnerability/v1/pipeline-results",
        }
        max_limit = RUNTIME_MAX_LIMIT if args.command == "runtime" else 1000
        if args.command == "registry":
            max_limit = REGISTRY_MAX_LIMIT
        params = {
            "cursor": args.cursor,
            "limit": _limit(args.limit, max_limit),
            "filter": _runtime_filter(args)
            if args.command == "runtime"
            else args.filter,
            "sort": args.sort if args.command == "runtime" else None,
        }
        path = paths[args.command]
        payload = _get(path, params, token, _host(args.host, path))
        rows = _runtime_rows(payload) if args.command == "runtime" else _basic_rows(payload)
        header = (
            "id", "asset", "type", "cluster", "namespace",
            "running_vulns", "total_vulns", "policy",
        ) if args.command == "runtime" else ("id", "name", "type", "status")
        _emit(payload, args.raw, header, rows)
        _show_cursor(payload)
        return 0
    if args.command == "result":
        path = f"/secure/vulnerability/v1/results/{args.id}"
        payload = _get(path, {}, token, _host(args.host, path))
        header = (
            "package", "version", "vuln", "severity", "exploitable",
            "exploit", "accepted_risks", "fixed_in",
        )
        _emit(payload, args.raw, header, _result_rows(payload))
        return 0
    if args.command == "sboms":
        params = {
            "assetId": args.assetId,
            "assetType": args.assetType,
            "bomIdentifier": args.bomIdentifier,
        }
        path = "/secure/vulnerability/v1beta1/sboms"
        payload = _get(path, params, token, _host(args.host, path))
        _emit(payload, args.raw, ("id", "name", "type", "status"), _basic_rows(payload))
        return 0
    if args.command == "inventory":
        params = {
            "filter": args.filter,
            "withEnrichedContainers": "true",
            "pageNumber": args.pageNumber,
            "pageSize": args.pageSize,
        }
        path = "/secure/inventory/v1/resources"
        payload = _get(path, params, token, _host(args.host, path))
        _emit(payload, args.raw, ("id", "name", "type", "status"), _basic_rows(payload))
        _show_cspm_page(payload, args.pageNumber, args.pageSize)
        return 0
    if args.command == "zones":
        params = {
            "filter": _zone_filter(args.filter),
        }
        path = "/platform/v1/zones"
        payload = _get(path, params, token, _host(args.host, path))
        _emit(payload, args.raw, ("id", "name", "type", "status"), _basic_rows(payload))
        return 0
    params = {
        "from": args.from_ns,
        "to": args.to_ns,
        "cursor": args.cursor,
        "limit": _limit(args.limit, 1000),
        "filter": args.filter,
    }
    path = "/api/v1/secureEvents"
    payload = _get(path, params, token, _host(args.host, path))
    _emit(payload, args.raw, ("id", "name", "type", "status"), _basic_rows(payload))
    _show_cursor(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
