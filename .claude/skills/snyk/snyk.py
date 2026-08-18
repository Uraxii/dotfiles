#!/usr/bin/env python3
"""Read-only Snyk REST query CLI.

Env: SNYK_TOKEN, optional SNYK_API_HOST. Example:
    snyk.py issues --org ORG_ID --severity high
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "2026-03-25"
DEFAULT_HOST = "api.snyk.io"
DEFAULT_LIMIT = 20
TIMEOUT_SEC = 30
JSON_API = "application/vnd.api+json"
MAX_ERROR_MESSAGE_CHARS = 200
# (low, high, step); step None means any value in range is valid.
# orgs/projects/issues declare multipleOf: 10 in the spec; targets and
# findings declare 1..100 with no step.
LIMITS = {
    "orgs": (10, 100, 10),
    "projects": (10, 100, 10),
    "issues": (10, 100, 10),
    "targets": (1, 100, None),
    "findings": (1, 100, None),
}
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
ISSUE_FIX_KEYS = (
    "is_fixable_snyk",
    "is_fixable_upstream",
    "is_fixable_manually",
)
__all__ = ["main"]


def _api() -> str:
    host = os.environ.get("SNYK_API_HOST", DEFAULT_HOST)
    host = host.removeprefix("https://").removeprefix("http://")
    host = host.rstrip("/").removesuffix("/rest")
    return f"https://{host}/rest"


def _token() -> str:
    token = os.environ.get("SNYK_TOKEN")
    if not token:
        sys.exit("missing SNYK_TOKEN")
    return token


def _check_limit(command: str, value: int) -> int:
    low, high, step = LIMITS.get(command, (1, 100, None))
    bad_range = value < low or value > high
    bad_step = step is not None and value % step != 0
    if bad_range or bad_step:
        step_msg = f", multiple of {step}" if step else ""
        sys.exit(
            f"--limit must be {low}-{high}{step_msg} for {command}, "
            f"got {value}"
        )
    return value


def _check_uuid(name: str, value: str) -> None:
    if not _UUID_RE.match(value):
        sys.exit(
            f"--{name} must be a UUID, got {value!r}; resolve a slug "
            "first with: snyk.py orgs --slug <slug>"
        )


def _url(path: str, params: dict[str, object]) -> str:
    return f"{_api()}{path}?{urllib.parse.urlencode(params, doseq=True)}"


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
        if not isinstance(error, dict):
            continue
        text = error.get("detail") or error.get("title")
        if isinstance(text, str) and text:
            messages.append(text[:MAX_ERROR_MESSAGE_CHARS])
    return "; ".join(messages) if messages else None


def _get(path_or_url: str, params: dict[str, object], token: str) -> dict:
    if path_or_url.startswith("https://"):
        url = path_or_url
    elif path_or_url.startswith("/") and not params:
        # args.next is a relative cursor path (no /rest prefix) that already
        # carries its own querystring verbatim; re-encoding would corrupt
        # the opaque starting_after value. Normal command paths always pass
        # non-empty params (version is always set), so this branch only
        # fires for the --next case.
        url = f"{_api()}{path_or_url}"
    else:
        url = _url(path_or_url, params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": JSON_API,
            "Content-Type": JSON_API,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            try:
                data = json.load(resp)
            except json.JSONDecodeError:
                sys.exit(
                    f"non-JSON response from {urllib.parse.urlparse(url).hostname}"
                )
    except urllib.error.HTTPError as err:
        status = f"HTTP {err.code} {err.reason}"
        message = _error_message(err.read())
        print(f"{status}\n{message}" if message else status, file=sys.stderr)
        sys.exit(1)
    return data if isinstance(data, dict) else {"data": data}


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
    data = payload.get("data", [])
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return [data] if isinstance(data, dict) else []


def _attrs(item: dict) -> dict:
    attrs = item.get("attributes", {})
    return attrs if isinstance(attrs, dict) else {}


def _csv(values: list[object]) -> str:
    return ",".join(str(value) for value in values if value not in (None, ""))


def _relationship_attrs(item: dict, name: str) -> dict:
    related = item.get("relationships", {}).get(name, {})
    data = related.get("data", {}) if isinstance(related, dict) else {}
    attrs = data.get("attributes", {}) if isinstance(data, dict) else {}
    return attrs if isinstance(attrs, dict) else {}


def _relationship_id(item: dict, name: str) -> object:
    related = item.get("relationships", {}).get(name, {})
    data = related.get("data", {}) if isinstance(related, dict) else {}
    return data.get("id", "-") if isinstance(data, dict) else "-"


def _coordinates(attrs: dict) -> list[dict]:
    coords = attrs.get("coordinates", [])
    return [item for item in coords if isinstance(item, dict)] if isinstance(
        coords, list
    ) else []


def _problem_id(attrs: dict) -> str:
    problems = attrs.get("problems", [])
    if not isinstance(problems, list):
        return "-"
    ids = [
        item.get("id")
        for item in problems
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    return _csv([value for value in ids if re.match(r"^CVE-\d{4}-\d+$", value)] or ids) or "-"


def _risk_score(attrs: dict) -> object:
    risk = attrs.get("risk", {})
    score = risk.get("score", {}) if isinstance(risk, dict) else {}
    return score.get("value", "-") if isinstance(score, dict) else "-"


def _risk_score_model(attrs: dict) -> object:
    risk = attrs.get("risk", {})
    score = risk.get("score", {}) if isinstance(risk, dict) else {}
    return score.get("model", "-") if isinstance(score, dict) else "-"


def _risk_factors(attrs: dict) -> str:
    risk = attrs.get("risk", {})
    if not isinstance(risk, dict) or "factors" not in risk:
        return "n/a"
    factors = risk.get("factors")
    if not isinstance(factors, list):
        return "n/a"
    names = [
        item.get("name")
        for item in factors
        if isinstance(item, dict) and item.get("value") is True
    ]
    return _csv(names) or "-"


def _reachability(attrs: dict) -> str:
    if "coordinates" not in attrs:
        return "n/a"
    values = []
    for coord in _coordinates(attrs):
        value = coord.get("reachability")
        if value not in values and value not in (None, ""):
            values.append(value)
    return _csv(values) or "-"


def _fixable(attrs: dict) -> bool:
    return any(
        coord.get(key) is True
        for coord in _coordinates(attrs)
        for key in ISSUE_FIX_KEYS
    )


def _org_rows(payload: dict) -> list[tuple[object, ...]]:
    return [(item.get("id"), _attrs(item).get("name"), _attrs(item).get("slug"))
            for item in _records(payload)]


def _self_rows(payload: dict) -> list[tuple[object, ...]]:
    return [
        (
            item.get("id"),
            item.get("type"),
            _attrs(item).get("name"),
            _attrs(item).get("username") or _attrs(item).get("email"),
        )
        for item in _records(payload)
    ]


def _project_rows(payload: dict) -> list[tuple[object, ...]]:
    rows = []
    for item in _records(payload):
        attrs = _attrs(item)
        target = _relationship_attrs(item, "target")
        rows.append((
            item.get("id"),
            attrs.get("name"),
            attrs.get("origin"),
            attrs.get("target_reference"),
            attrs.get("target_file"),
            target.get("display_name"),
            target.get("url"),
        ))
    return rows


def _target_rows(payload: dict) -> list[tuple[object, ...]]:
    return [
        (
            item.get("id"),
            _attrs(item).get("display_name"),
            _attrs(item).get("url"),
            _attrs(item).get("is_private"),
        )
        for item in _records(payload)
    ]


def _issue_rows(payload: dict) -> list[tuple[object, ...]]:
    rows = []
    for item in _records(payload):
        attrs = _attrs(item)
        rows.append((
            item.get("id"),
            attrs.get("effective_severity_level"),
            attrs.get("status"),
            attrs.get("type"),
            _problem_id(attrs),
            _risk_score(attrs),
            _risk_score_model(attrs),
            _risk_factors(attrs),
            _reachability(attrs),
            _fixable(attrs),
            _relationship_id(item, "scan_item"),
        ))
    return rows


def _finding_rows(payload: dict) -> list[tuple[object, ...]]:
    rows = []
    for item in _records(payload):
        epss = "-"
        attrs = _attrs(item)
        problems = attrs.get("problems", [])
        for problem in problems if isinstance(problems, list) else []:
            details = problem.get("epss_details", {}) if isinstance(problem, dict) else {}
            if isinstance(details, dict) and details.get("probability"):
                epss = details.get("probability")
                break
        rows.append((item.get("id"), _problem_id(attrs), epss))
    return rows


def _base_params(args: argparse.Namespace) -> dict[str, object]:
    params: dict[str, object] = {"version": args.version}
    if hasattr(args, "limit"):
        params["limit"] = _check_limit(args.command, args.limit)
    for arg, key in (("starting_after", "starting_after"),
                     ("ending_before", "ending_before")):
        value = getattr(args, arg, None)
        if value:
            params[key] = value
    return params


def _add_common(cmd: argparse.ArgumentParser, paged: bool = True) -> None:
    cmd.add_argument("--version", default=API_VERSION, help="Snyk API version")
    cmd.add_argument("--next", help="fetch this links.next relative path verbatim")
    cmd.add_argument("--raw", action="store_true")
    if paged:
        cmd.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
        cmd.add_argument("--starting-after")
        cmd.add_argument("--ending-before")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    orgs = sub.add_parser("orgs")
    _add_common(orgs)
    orgs.add_argument("--group-id")
    orgs.add_argument("--slug")
    orgs.add_argument("--is-personal")
    orgs.add_argument("--name")
    self_cmd = sub.add_parser("self")
    _add_common(self_cmd, paged=False)
    for name in ("projects", "targets"):
        cmd = sub.add_parser(name)
        _add_common(cmd)
        cmd.add_argument("--org")
    sub.choices["projects"].add_argument("--target-id", action="append")
    sub.choices["projects"].add_argument("--origin", action="append")
    sub.choices["projects"].add_argument("--tag", action="append")
    sub.choices["projects"].add_argument("--ids", action="append")
    sub.choices["projects"].add_argument("--names", action="append")
    sub.choices["projects"].add_argument("--types", action="append")
    sub.choices["projects"].add_argument("--target-reference")
    sub.choices["projects"].add_argument("--target-file")
    sub.choices["projects"].add_argument("--business-criticality")
    sub.choices["projects"].add_argument("--environment")
    sub.choices["projects"].add_argument("--lifecycle")
    # server default for exclude_empty is true; this tool sends false
    # unless the caller overrides it (see DEFECTS-snyk-live-spec.md #1).
    sub.choices["targets"].add_argument("--exclude-empty", default="false")
    sub.choices["targets"].add_argument("--is-private")
    sub.choices["targets"].add_argument("--url")
    sub.choices["targets"].add_argument("--source-types", action="append")
    sub.choices["targets"].add_argument("--display-name")
    sub.choices["targets"].add_argument("--created-gte")
    sub.choices["targets"].add_argument("--count")
    issues = sub.add_parser("issues")
    _add_common(issues)
    scope = issues.add_mutually_exclusive_group()
    scope.add_argument("--org")
    scope.add_argument("--group")
    for name in ("type", "ignored", "scan-item-id", "scan-item-type",
                 "updated-after", "created-after", "created-before",
                 "updated-before"):
        issues.add_argument(f"--{name}")
    issues.add_argument("--severity", action="append")
    issues.add_argument("--status", action="append")
    issue = sub.add_parser("issue")
    _add_common(issue, paged=False)
    issue.add_argument("--org")
    issue.add_argument("--id")
    findings = sub.add_parser("findings", help=(
        "Early Access findings endpoint, only Snyk REST source for EPSS. "
        "--test comes from a `snyk` CLI run or a prior POST "
        "/orgs/{org_id}/tests; this read-only tool cannot obtain one."
    ))
    _add_common(findings)
    findings.add_argument("--org")
    findings.add_argument("--test")
    return parser


_REQUIRED_SCOPE = {
    "projects": ("org",), "targets": ("org",),
    "issue": ("org", "id"), "findings": ("org", "test"),
}


def _validate_scope(args: argparse.Namespace) -> None:
    if args.command == "issues":
        if not args.org and not args.group:
            sys.exit("issues requires --org or --group")
        if bool(args.scan_item_id) != bool(args.scan_item_type):
            sys.exit(
                "--scan-item-id and --scan-item-type must be used together"
            )
    else:
        for name in _REQUIRED_SCOPE.get(args.command, ()):
            if not getattr(args, name, None):
                sys.exit(f"{args.command} requires --{name}")
    if getattr(args, "org", None):
        _check_uuid("org", args.org)
    if getattr(args, "group", None):
        _check_uuid("group", args.group)
    if getattr(args, "group_id", None):
        _check_uuid("group-id", args.group_id)
    for value in getattr(args, "target_id", None) or ():
        _check_uuid("target-id", value)


def _request(args: argparse.Namespace) -> tuple[str, dict[str, object]]:
    params = _base_params(args)
    if args.command == "orgs":
        for arg, key in (("group_id", "group_id"), ("slug", "slug"),
                          ("is_personal", "is_personal"), ("name", "name")):
            value = getattr(args, arg, None)
            if value:
                params[key] = value
        return "/orgs", params
    if args.command == "self":
        return "/self", params
    if args.command == "projects":
        params["expand"] = "target"
        # target_id has no style/explode in the spec, so it defaults to
        # explode: true (repeated key); doseq in _url does that for a list.
        for arg, key in (("target_id", "target_id"), ("ids", "ids"),
                          ("names", "names"), ("types", "types")):
            value = getattr(args, arg, None)
            if value:
                params[key] = value
        # origins/tags are style: form, explode: false: one comma-joined param.
        if args.origin:
            params["origins"] = _csv(args.origin)
        if args.tag:
            params["tags"] = _csv(args.tag)
        for arg, key in (("target_reference", "target_reference"),
                          ("target_file", "target_file"),
                          ("business_criticality", "business_criticality"),
                          ("environment", "environment"),
                          ("lifecycle", "lifecycle")):
            value = getattr(args, arg, None)
            if value:
                params[key] = value
        return f"/orgs/{args.org}/projects", params
    if args.command in ("targets", "issue", "findings"):
        # per-branch, not a dict literal: a dict literal eagerly evaluates
        # every f-string, and args.id / args.test do not exist on the
        # Namespace unless that subcommand actually added them.
        if args.command == "targets":
            suffix = "targets"
        elif args.command == "issue":
            suffix = f"issues/{args.id}"
        else:
            suffix = f"tests/{args.test}/findings"
        if args.command == "targets":
            # server default is true; always send our own default explicitly.
            params["exclude_empty"] = args.exclude_empty
            for arg, key in (("is_private", "is_private"), ("url", "url"),
                              ("display_name", "display_name"),
                              ("created_gte", "created_gte"),
                              ("count", "count")):
                value = getattr(args, arg, None)
                if value:
                    params[key] = value
            if args.source_types:
                params["source_types"] = args.source_types
        return f"/orgs/{args.org}/{suffix}", params
    if args.severity:
        params["effective_severity_level"] = _csv(args.severity)
    if args.status:
        params["status"] = _csv(args.status)
    for arg, key in (("type", "type"), ("ignored", "ignored"),
                     ("scan_item_id", "scan_item.id"),
                     ("scan_item_type", "scan_item.type"),
                     ("updated_after", "updated_after"),
                     ("created_after", "created_after"),
                     ("created_before", "created_before"),
                     ("updated_before", "updated_before")):
        value = getattr(args, arg, None)
        if value:
            params[key] = value
    scope = f"/orgs/{args.org}" if args.org else f"/groups/{args.group}"
    return f"{scope}/issues", params


def _header_and_rows(
    command: str, payload: dict
) -> tuple[tuple[str, ...], list[tuple[object, ...]]]:
    tables = {
        "orgs": (("id", "name", "slug"), _org_rows),
        "self": (("id", "type", "name", "user"), _self_rows),
        "projects": (
            ("id", "name", "origin", "branch", "manifest", "repo", "repo_url"),
            _project_rows,
        ),
        "targets": (("id", "display_name", "url", "private"), _target_rows),
        "findings": (("id", "problem", "epss_probability"), _finding_rows),
    }
    if command in tables:
        header, rows = tables[command]
        return header, rows(payload)
    return (
        ("id", "severity", "status", "type", "problem", "risk", "risk_model",
         "factors", "reachability", "fixable", "scan_item_id"),
        _issue_rows(payload),
    )


def _next_cursor(payload: dict) -> str | None:
    links = payload.get("links", {})
    next_link = links.get("next") if isinstance(links, dict) else None
    if isinstance(next_link, dict):
        # links.next is oneOf [string, {href, meta}]; unwrap the object form.
        next_link = next_link.get("href")
    return next_link if isinstance(next_link, str) and next_link else None


def _show_next(payload: dict) -> None:
    cursor = _next_cursor(payload)
    if cursor:
        # stdout, not stderr: a truncated page must not look complete to a
        # caller that only captures stdout.
        print(f"next: {cursor}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = _token()
    if args.next:
        payload = _get(args.next, {}, token)
    else:
        _validate_scope(args)
        path, params = _request(args)
        payload = _get(path, params, token)
    if args.raw:
        print(json.dumps(payload, separators=(",", ":")))
    else:
        header, rows = _header_and_rows(args.command, payload)
        _print(header, rows)
    _show_next(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
