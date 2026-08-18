---
name: snyk
description: Query Snyk REST API orgs, token identity, projects, targets, issues, issue details, and Early Access findings for read-only inventory and vulnerability prioritization.
---

# snyk

Thin Snyk REST reader. It is read-only, GET only, and cannot change anything
in the vendor tenant.

The majority of Snyk APIs are Enterprise-plan only, and Free/Team personal
tokens cannot use the Snyk REST API at all. Those tokens are limited to
IDE/CLI/CI use.

Required env: `SNYK_TOKEN`. Optional env: `SNYK_API_HOST`.

`SNYK_API_HOST` defaults to `api.snyk.io`. Region hosts include `api.us.snyk.io`,
`api.eu.snyk.io`, and `api.au.snyk.io`; tokens are region-bound.

Default API version: `2026-03-25`. Override per command with `--version`.
Snyk REST rate limit: 1620 calls per minute per key.

`--org`, `--group`, `--group-id`, and `--target-id` must be UUIDs, not slugs;
the tool rejects a slug locally. Resolve a slug to an id first with
`orgs --slug <slug>`.

`projects`, `targets`, and `issues` take extra filter flags beyond the
examples below (`--ids`/`--names`/`--types`/`--target-reference`/
`--target-file`/`--business-criticality`/`--environment`/`--lifecycle` on
`projects`; `--is-private`/`--url`/`--source-types`/`--display-name`/
`--created-gte`/`--count`/`--exclude-empty` on `targets`;
`--created-after`/`--created-before`/`--updated-before` on `issues`). Run
`snyk.py <command> --help` for the full flag list.

## Can answer

- Which Snyk orgs are visible to this token, optionally by group or slug.
- Which token identity is in use.
- Which projects and targets exist in an org.
- Which org or group issues exist, filtered by severity, status, type, ignored
  state, scan item, and update time.
- Which prioritization signals Snyk exposes on issues: risk score, true
  `risk.factors[]`, reachability, and fixability.
- Which issue details exist for one org issue ID.
- Which findings exist for one test ID, IF a test ID is already in hand. This
  is the only Snyk REST surface here that exposes EPSS.

## Cannot answer

- No writes.
- No cross-vendor correlation.
- No historical trending.
- No EPSS from `/issues`; use `findings` for EPSS.
- No KEV field. The only related signal is the literal string `CISA` inside
  `exploit_details.sources[]`, visible only with `--raw`.
- `findings --test` needs a `test_id`, obtainable only by POSTing
  `/orgs/{org_id}/tests`. This read-only tool never does that POST, so
  `--test` must come from a `snyk` CLI run or a prior POST done elsewhere;
  the `findings` subcommand is otherwise unreachable from this tool alone.

## Use it

```bash
python3 ~/.claude/skills/snyk/snyk.py orgs --slug platform
# illustrative output:
id	name	slug
org-1	Platform	platform
```

```bash
python3 ~/.claude/skills/snyk/snyk.py self
# illustrative output:
id	type	name	user
user-1	user	Example User	-
```

```bash
python3 ~/.claude/skills/snyk/snyk.py projects --org $ORG_ID --target-id target-1
# illustrative output:
id	name	origin	branch	manifest	repo	repo_url
p1	api	github	main	package.json	org/api	https://github.com/org/api
```

```bash
python3 ~/.claude/skills/snyk/snyk.py targets --org $ORG_ID --limit 10
# illustrative output:
id	display_name	url	private
t1	org/api	https://github.com/org/api	false
```

`targets` always sends `exclude_empty=false` (the server default is `true`,
which silently drops every target with zero projects). Pass
`--exclude-empty true` to restore the server default.

```bash
python3 ~/.claude/skills/snyk/snyk.py issues --org $ORG_ID --severity high --severity critical
# illustrative output:
id	severity	status	type	problem	risk	risk_model	factors	reachability	fixable	scan_item_id
i1	high	open	package_vulnerability	CVE-2026-0001	891	riskScore	deployed,loaded_package	function	true	p1
```

`risk` and `risk_model` come from `attributes.risk.score.{value,model}` (the
GA field can carry either the legacy priority score or the newer Risk Score,
distinguished by `risk_model`). `factors` and `reachability` print `n/a` when
the whole field is absent from the response (unentitled tenant) and `-` only
when the field is present but empty (entitled, nothing found); the two cases
were previously indistinguishable. Multiple `--severity`/`--status` values
are sent as one comma-joined parameter (`effective_severity_level=high,critical`);
`--target-id` on `projects` is repeated instead (`target_id=a&target_id=b`),
per how each parameter is declared in the spec.

```bash
python3 ~/.claude/skills/snyk/snyk.py issue --org $ORG_ID --id issue-1 --raw
# illustrative output:
{"jsonapi":{"version":"1.0"},"data":{"id":"issue-1"}}
```

```bash
python3 ~/.claude/skills/snyk/snyk.py findings --org $ORG_ID --test test-1
# illustrative output:
id	problem	epss_probability
finding-1	CVE-2026-0001	0.0042
```

For pagination, pass the exact value printed as `next:` verbatim. The API
returns a relative path (no `/rest` prefix, already carrying `version` and
`starting_after`), so pass it as-is, quoted:

```bash
python3 ~/.claude/skills/snyk/snyk.py issues --next '/orgs/org-1/issues?version=2026-03-25&starting_after=opaque&limit=20'
```

No scope flags (`--org`/`--group`/`--id`/`--test`) are needed alongside
`--next`; the tool fetches the cursor path verbatim and skips scope
validation entirely when `--next` is given. `links.next` may also arrive as
an object (`{"href": ..., "meta": {...}}`) instead of a bare string; the
tool unwraps `href` either way, so always pass the value printed after
`next:` unmodified.

## Verified

This surface was verified against the VERSIONED public no-auth Snyk REST spec
`https://api.snyk.io/rest/openapi/2026-03-25` on 2026-08-18. The bare URL
`https://api.snyk.io/rest/openapi` (no version segment) returns only a JSON
array of version strings, no schemas, and must not be cited as the source.

Verified endpoints:

- `GET /orgs`
- `GET /self`
- `GET /orgs/{org_id}/projects`
- `GET /orgs/{org_id}/targets`
- `GET /orgs/{org_id}/issues`
- `GET /groups/{group_id}/issues`
- `GET /orgs/{org_id}/issues/{issue_id}`
- `GET /orgs/{org_id}/tests/{test_id}/findings`

Verified request rules:

- Every request sends `version`.
- Auth is `Authorization: token <TOKEN>`.
- `Accept` and `Content-Type` are `application/vnd.api+json`.
- Pagination uses opaque `starting_after` and `ending_before` cursors plus
  `limit`; `links.next` is a relative path (no `/rest` prefix) that already
  carries its own querystring and must be fetched verbatim, with no
  parameter re-encoding.
- Limit bounds: `orgs`, `projects`, and `issues` (org- or group-scoped) are
  10 to 100 AND a multiple of 10 (`multipleOf: 10` in the spec); `targets`
  and `findings` are 1 to 100 with no step. An out-of-range or wrong-step
  `--limit` is rejected locally, never silently rounded.
- `targets` server-side default for `exclude_empty` is `true`; this tool
  always sends `exclude_empty=false` unless `--exclude-empty` overrides it.
- `findings` is `x-snyk-api-stability: beta` and resolves under a plain date
  version string. No `~experimental`-suffixed version exists for it after
  2024-10-15.

## Unverified

- Live tenant entitlement behavior was not exercised. Snyk has never been
  run against a live API from this tool.
- Does every endpoint 400 on an unknown parameter, or do some ignore it
  silently instead?
- Do comma-joined filter values encoded as `%2C` split server-side, or is a
  literal comma required (a `quote_via` question)?
- Default `status`/`ignored` behavior of `/orgs/{org_id}/issues` when
  neither filter is sent.
- Does `links.next` ever appear in its object form (`{href, meta}`) in
  production? Every recorded fixture so far is a bare string.
- Does a non-Enterprise or under-permissioned token return a clean 403, or a
  200 with an empty `data[]`? The latter would be another silent-empty.
