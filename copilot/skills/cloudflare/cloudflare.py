#!/usr/bin/env python3
"""Read-only Cloudflare API query CLI.

Env: CLOUDFLARE_API_TOKEN. Example:
    cloudflare.py dns --zone ZONE_ID --proxied false
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.cloudflare.com/client/v4/"
TIMEOUT_SEC = 30
MAX_ERROR_MESSAGE_CHARS = 200
MIN_REQUEST_INTERVAL_SEC = 0.25
OWASP_CORE_RULESET_ID = "4814384a9e5d4991b9815dcfc25d2f1f"
SCORE_THRESHOLD_RULE_ID = "6179ae15870a4bb7b2d480d4843b323c"
MAX_RETRY_AFTER_SEC = 60
DNS_MAX_PER_PAGE = 5000
RULESET_PHASES = (
    "ddos_l4", "ddos_l7", "http_config_settings", "http_custom_errors",
    "http_log_custom_fields", "http_ratelimit",
    "http_request_cache_settings", "http_request_dynamic_redirect",
    "http_request_firewall_custom", "http_request_firewall_managed",
    "http_request_late_transform", "http_request_origin",
    "http_request_redirect", "http_request_sanitize", "http_request_sbfm",
    "http_request_transform", "http_response_cache_settings",
    "http_response_compression", "http_response_firewall_managed",
    "http_response_headers_transform", "magic_transit",
    "magic_transit_ids_managed", "magic_transit_managed",
    "magic_transit_ratelimit",
)
RULESET_KINDS = ("managed", "custom", "root", "zone")
SCORE_LABELS = {60: "Low", 40: "Medium", 25: "High"}
_LAST_REQUEST_AT = 0.0
__all__ = ["main"]


def _token() -> str:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        sys.exit("missing CLOUDFLARE_API_TOKEN")
    return token


def _sleep_needed(now: float, last: float) -> float:
    return max(0.0, MIN_REQUEST_INTERVAL_SEC - (now - last))


def _throttle(clock=time.monotonic, sleep=time.sleep) -> None:
    global _LAST_REQUEST_AT
    delay = _sleep_needed(clock(), _LAST_REQUEST_AT)
    if delay:
        sleep(delay)
    _LAST_REQUEST_AT = clock()


def _clean(params: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in params.items() if v is not None}


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


def _get(
    path: str, params: dict[str, object], token: str, _retried: bool = False
) -> dict:
    _throttle()
    query = urllib.parse.urlencode(_clean(params))
    url = f"{API}{path.lstrip('/')}"
    if query:
        url = f"{url}?{query}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            try:
                return _check(json.load(resp))
            except json.JSONDecodeError:
                sys.exit(
                    f"non-JSON response from {urllib.parse.urlparse(url).hostname}"
                )
    except urllib.error.HTTPError as err:
        if err.code == 429 and not _retried:
            retry = err.headers.get("Retry-After")
            if retry and retry.isdigit():
                time.sleep(min(int(retry), MAX_RETRY_AFTER_SEC))
            return _get(path, params, token, _retried=True)
        status = f"HTTP {err.code} {err.reason}"
        message = _error_message(err.read())
        print(f"{status}\n{message}" if message else status, file=sys.stderr)
        sys.exit(1)


def _check(payload: dict) -> dict:
    if payload.get("success", True):
        return payload
    errors = payload.get("errors") or [{"message": "Cloudflare API failed"}]
    text = "; ".join(
        str(err.get("message", err)) if isinstance(err, dict) else str(err)
        for err in errors
    )
    sys.exit(text)


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
    data = payload.get("result", [])
    return data if isinstance(data, list) else []


def _account_rows(payload: dict) -> list[tuple[object, ...]]:
    return [(item.get("id"), item.get("name")) for item in _records(payload)]


def _zone_rows(payload: dict) -> list[tuple[object, ...]]:
    return [
        (item.get("id"), item.get("name"), item.get("status"),
         item.get("type"), item.get("paused"),
         (item.get("account") or {}).get("name"))
        for item in _records(payload)
    ]


def _dns_rows(payload: dict) -> list[tuple[object, ...]]:
    return [
        (item.get("name"), item.get("type"), item.get("content"),
         item.get("proxied"), item.get("ttl"))
        for item in _records(payload)
    ]


def _ruleset_rows(payload: dict) -> list[tuple[object, ...]]:
    return [
        (item.get("id"), item.get("name"), item.get("kind"),
         item.get("phase"), item.get("version"), item.get("last_updated"))
        for item in _records(payload)
    ]


def _ruleset_row(payload: dict) -> list[tuple[object, ...]]:
    item = payload.get("result", {})
    return [(item.get("id"), item.get("name"), item.get("kind"),
             item.get("phase"), item.get("version"), len(item.get("rules", [])))]


def _routes_rows(payload: dict) -> list[tuple[object, ...]]:
    return [(item.get("pattern"), item.get("script")) for item in _records(payload)]


def _waf_rows(payload: dict) -> list[tuple[object, ...]]:
    rows = []
    result = payload.get("result", {})
    for rule in result.get("rules", []):
        if rule.get("action") != "execute":
            continue
        enabled = rule.get("enabled", True)
        params = rule.get("action_parameters", {})
        ruleset_id = params.get("id")
        if ruleset_id != OWASP_CORE_RULESET_ID:
            rows.append((ruleset_id, "-", "-", "-", "-", enabled))
            continue
        overrides = params.get("overrides", {})
        pl = _paranoia(overrides.get("categories", []))
        threshold = _score_threshold(overrides.get("rules", []))
        rows.append(
            (ruleset_id, "OWASP Core Ruleset", pl, _score_label(threshold),
             threshold, enabled)
        )
    return rows


def _paranoia(categories: list[dict]) -> str:
    enabled = [
        (item.get("category") or "").replace("paranoia-level-", "PL")
        for item in categories
        if (item.get("category") or "").startswith("paranoia-level-")
        and item.get("enabled") is True
    ]
    return ",".join(enabled) if enabled else "PL1"


def _score_threshold(rules: list[dict]) -> int:
    for rule in rules:
        if rule.get("id") == SCORE_THRESHOLD_RULE_ID:
            value = rule.get("score_threshold")
            if isinstance(value, int):
                return value
    return 40


def _score_label(score: int) -> str:
    return SCORE_LABELS.get(score, "Custom")


def _show_page(payload: dict) -> None:
    info = payload.get("result_info", {})
    if not isinstance(info, dict) or not info:
        return
    cursors = info.get("cursors")
    cursor_after = cursors.get("after") if isinstance(cursors, dict) else None
    cursor = info.get("cursor") or cursor_after
    if cursor:
        print(f"next cursor {cursor}", file=sys.stderr)
        return
    if "page" not in info and "total_pages" not in info:
        return
    print(
        f"page {info.get('page', '-')} of {info.get('total_pages', '-')} "
        f"({info.get('count', '-')} of {info.get('total_count', '-')})",
        file=sys.stderr,
    )


def _bool(value: str) -> str:
    if value.lower() not in ("true", "false"):
        raise argparse.ArgumentTypeError("expected true or false")
    return value.lower()


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _filters(args: argparse.Namespace, names: tuple[str, ...]) -> dict[str, object]:
    return {name: getattr(args, name.replace(".", "_")) for name in names}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    accounts = sub.add_parser("accounts")
    accounts.add_argument("--name")
    accounts.add_argument("--page", type=int, default=1)
    accounts.add_argument("--per-page", "--limit", dest="per_page", type=int,
                          default=20)
    accounts.add_argument("--raw", action="store_true")

    zones = sub.add_parser("zones")
    for name in ("name", "status", "type", "account.id", "account.name",
                 "order", "direction", "match"):
        zones.add_argument(f"--{name}", dest=name.replace(".", "_"))
    zones.add_argument("--page", type=int, default=1)
    zones.add_argument("--per-page", "--limit", dest="per_page", type=int,
                       default=20)
    zones.add_argument("--raw", action="store_true")

    dns = sub.add_parser("dns")
    dns.add_argument("--zone", required=True)
    dns.add_argument("--proxied", type=_bool)
    for name in ("type", "name", "content", "search", "match", "tag",
                 "order", "direction"):
        dns.add_argument(f"--{name}")
    dns.add_argument("--page", type=int, default=1)
    dns.add_argument("--per-page", "--limit", dest="per_page", type=int,
                     default=100)
    dns.add_argument("--raw", action="store_true")

    rulesets = sub.add_parser(
        "rulesets",
        description="List metadata only. Rules require ruleset --id.",
    )
    group = rulesets.add_mutually_exclusive_group(required=True)
    group.add_argument("--zone")
    group.add_argument("--account")
    rulesets.add_argument("--cursor")
    rulesets.add_argument("--per-page", "--limit", dest="per_page", type=int,
                          default=50)
    rulesets.add_argument("--phase", choices=RULESET_PHASES)
    rulesets.add_argument("--kind", choices=RULESET_KINDS)
    rulesets.add_argument("--raw", action="store_true")

    ruleset = sub.add_parser("ruleset")
    ruleset.add_argument("--zone", required=True)
    ruleset.add_argument("--id", required=True)
    ruleset.add_argument("--raw", action="store_true")

    waf = sub.add_parser("waf")
    waf.add_argument("--zone", required=True)
    waf.add_argument("--raw", action="store_true")

    routes = sub.add_parser("routes")
    routes.add_argument("--zone", required=True)
    routes.add_argument("--raw", action="store_true")
    return parser


def _request(args: argparse.Namespace) -> tuple[str, dict[str, object], tuple, object]:
    if args.command == "accounts":
        return "/accounts", {
            "name": args.name, "page": args.page,
            "per_page": _clamp(args.per_page, 5, 50),
        }, ("id", "name"), _account_rows
    if args.command == "zones":
        params = _filters(args, (
            "name", "status", "type", "account.id", "account.name",
            "order", "direction", "match",
        ))
        params.update({"page": args.page,
                       "per_page": _clamp(args.per_page, 5, 50)})
        return "/zones", params, (
            "id", "name", "status", "type", "paused", "account",
        ), _zone_rows
    if args.command == "dns":
        params = _filters(args, (
            "proxied", "type", "name", "content", "search", "match", "tag",
            "order", "direction",
        ))
        params.update({"page": args.page,
                       "per_page": _clamp(args.per_page, 1, DNS_MAX_PER_PAGE)})
        return f"/zones/{args.zone}/dns_records", params, (
            "name", "type", "content", "proxied", "ttl",
        ), _dns_rows
    if args.command == "rulesets":
        scope = f"zones/{args.zone}" if args.zone else f"accounts/{args.account}"
        params = {
            "cursor": args.cursor, "per_page": _clamp(args.per_page, 1, 50),
            "phase": args.phase, "kind": args.kind,
        }
        return f"/{scope}/rulesets", params, (
            "id", "name", "kind", "phase", "version", "last_updated",
        ), _ruleset_rows
    if args.command == "ruleset":
        return f"/zones/{args.zone}/rulesets/{args.id}", {}, (
            "id", "name", "kind", "phase", "version", "rules",
        ), _ruleset_row
    if args.command == "waf":
        return (
            f"/zones/{args.zone}/rulesets/phases/"
            "http_request_firewall_managed/entrypoint"
        ), {}, ("id", "name", "paranoia", "sensitivity", "threshold", "enabled"), _waf_rows
    return f"/zones/{args.zone}/workers/routes", {}, (
        "pattern", "script",
    ), _routes_rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path, params, header, rows = _request(args)
    payload = _get(path, params, _token())
    if args.raw:
        print(json.dumps(payload, separators=(",", ":")))
    else:
        _print(header, rows(payload))
    _show_page(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
