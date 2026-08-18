---
name: cloudflare
description: Query Cloudflare accounts, zones, DNS exposure, rulesets, WAF managed ruleset posture, and Workers routes from the public Cloudflare API.
---

# cloudflare

Thin Cloudflare API reader. It is read-only, GET only, and cannot change
anything in the vendor tenant.

Required env: `CLOUDFLARE_API_TOKEN`.

Optional env: none.

## Can answer

- Which accounts and zones are visible to this token.
- Which DNS records exist in a zone, with `proxied` as the exposure flag.
- Which zone or account rulesets exist by id, name, kind, phase, and version.
- Which rules exist in one zone ruleset, via `ruleset --zone ID --id RULESET_ID`.
- Which managed WAF rulesets are deployed (enabled) at the zone entrypoint,
  including OWASP Core Ruleset posture from paranoia level and score
  threshold overrides. Non-OWASP managed rulesets (Cloudflare Managed,
  Exposed Credentials) show `-` for paranoia/threshold; those fields do not
  exist on them, so no default is guessed.
- Which Cloudflare Workers routes exist in a zone.

## Cannot answer

- No writes.
- No cross-vendor correlation.
- No historical trending.
- No deprecated Firewall Rules API or Filters API. Unsupported since
  2025-06-15; use Rulesets.
- No GraphQL analytics or `firewallEventsAdaptive`. That is a POST endpoint,
  needs Account Analytics: Read, and is not in Cloudflare's OpenAPI.

## Use it

```bash
python3 ~/.claude/skills/cloudflare/cloudflare.py accounts
# illustrative output:
id	name
a1	Example Inc
```

```bash
python3 ~/.claude/skills/cloudflare/cloudflare.py zones --account.name "Example Inc"
# illustrative output:
id	name	status	type	paused	account
z1	example.com	active	full	false	Example Inc
```

```bash
python3 ~/.claude/skills/cloudflare/cloudflare.py dns --zone z1 --proxied false
# illustrative output:
name	type	content	proxied	ttl
origin.example.com	A	192.0.2.10	false	1
```

```bash
python3 ~/.claude/skills/cloudflare/cloudflare.py rulesets --zone z1 \
  --phase http_request_firewall_custom
# illustrative output:
id	name	kind	phase	version	last_updated
rs1	Custom WAF	zone	http_request_firewall_custom	3	2026-01-01
```

Ruleset list responses omit rules by design. Fetch one ruleset by id to see its
rules:

```bash
python3 ~/.claude/skills/cloudflare/cloudflare.py ruleset --zone z1 --id rs1
# illustrative output:
id	name	kind	phase	version	rules
rs1	Custom WAF	zone	http_request_firewall_custom	3	12
```

```bash
python3 ~/.claude/skills/cloudflare/cloudflare.py waf --zone z1
# illustrative output:
id	name	paranoia	sensitivity	threshold	enabled
4814384a9e5d4991b9815dcfc25d2f1f	OWASP Core Ruleset	PL2	Medium	40	True
```

If a zone has no custom entrypoint ruleset deployed in this phase, the API
returns a 404. That means no custom deployment, not no protection: default
managed rulesets (e.g. Cloudflare Managed Free Ruleset) can still be active.
The tool exits 0 and still writes an answer to stdout: plain text
`no entrypoint ruleset is deployed for this phase` by default, or with
`--raw` a small JSON object (`{"result":null,"no_entrypoint_ruleset":true,
"phase":"http_request_firewall_managed"}`). A longer explanation goes to
stderr. Run `rulesets --zone ZONE_ID` on the same zone to see what is
deployed.

```bash
python3 ~/.claude/skills/cloudflare/cloudflare.py routes --zone z1
# illustrative output:
pattern	script
example.com/app/*	app-worker
```

Common ruleset phases: WAF custom `http_request_firewall_custom`, WAF managed
`http_request_firewall_managed`, rate limiting `http_ratelimit`, DDoS
`ddos_l7` or `ddos_l4`, Super Bot Fight Mode `http_request_sbfm`.

## Verified

Verified against Cloudflare's public OpenAPI from `github.com/cloudflare/api-schemas`
`info.version` 4.0.0 on 2026-08-18.

The tool uses `https://api.cloudflare.com/client/v4/`, bearer auth from
`CLOUDFLARE_API_TOKEN`, and the required `{result, success, errors, messages}`
envelope. It checks `success` and surfaces `errors[]`.

Most list endpoints use offset pagination with `page` and `per_page`.
Rulesets use cursor pagination; the tool reads both `result_info.cursor`
(flat, what the official SDKs use) and `result_info.cursors.after` (what the
docs show), and ruleset rules require
`GET /zones/{zone_id}/rulesets/{ruleset_id}`.

DNS `--per-page` is clamped to 5,000 (the real-world cap), not the
documented 5,000,000.

Cloudflare's rate limit is 1,200 calls per 5 minutes per user, plus 200 per
second per IP. The tool self-throttles to a 0.25 second call floor and honors
`Retry-After` on 429.

Confirmed against a live account: `accounts`, `zones`, `dns` (filters and
page paging), `rulesets` (cursor paging), `ruleset`, and `routes`. The OWASP
paranoia/threshold projection in `waf` remains unverified live; it needs a
plan with the OWASP Core Ruleset deployed.
