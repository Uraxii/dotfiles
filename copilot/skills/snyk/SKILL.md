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

## Can answer

- Which Snyk orgs are visible to this token, optionally by group or slug.
- Which token identity is in use.
- Which projects and targets exist in an org.
- Which org or group issues exist, filtered by severity, status, type, ignored
  state, scan item, and update time.
- Which prioritization signals Snyk exposes on issues: risk score, true
  `risk.factors[]`, reachability, and fixability.
- Which issue details exist for one org issue ID.
- Which findings exist for one test ID. This Early Access endpoint is the only
  Snyk REST surface here that exposes EPSS.

## Cannot answer

- No writes.
- No cross-vendor correlation.
- No historical trending.
- No EPSS from `/issues`; use `findings` for EPSS.
- No KEV field. The only related signal is the literal string `CISA` inside
  `exploit_details.sources[]`, visible only with `--raw`.

## Use it

```bash
python3 ~/.copilot/skills/snyk/snyk.py orgs --slug platform
# illustrative output:
id	name	slug
org-1	Platform	platform
```

```bash
python3 ~/.copilot/skills/snyk/snyk.py self
# illustrative output:
id	type	name	user
user-1	user	Example User	-
```

```bash
python3 ~/.copilot/skills/snyk/snyk.py projects --org org-1 --target-id target-1
# illustrative output:
id	name	origin	branch	manifest	repo	repo_url
p1	api	github	main	package.json	org/api	https://github.com/org/api
```

```bash
python3 ~/.copilot/skills/snyk/snyk.py targets --org org-1 --limit 5
# illustrative output:
id	display_name	url	private
t1	org/api	https://github.com/org/api	false
```

```bash
python3 ~/.copilot/skills/snyk/snyk.py issues --org org-1 --severity high
# illustrative output:
id	severity	status	type	problem	risk	factors	reachability	fixable
i1	high	open	package_vulnerability	CVE-2026-0001	891	deployed,loaded_package	function	true
```

```bash
python3 ~/.copilot/skills/snyk/snyk.py issue --org org-1 --id issue-1 --raw
# illustrative output:
{"jsonapi":{"version":"1.0"},"data":{"id":"issue-1"}}
```

```bash
python3 ~/.copilot/skills/snyk/snyk.py findings --org org-1 --test test-1
# illustrative output:
id	problem	epss_probability
finding-1	CVE-2026-0001	0.0042
```

For pagination, pass the exact value printed as `next:` verbatim. The API
returns a relative path (no `/rest` prefix, already carrying `version` and
`starting_after`), so pass it as-is, quoted:

```bash
python3 ~/.copilot/skills/snyk/snyk.py issues --org org-1 --next '/orgs/org-1/issues?version=2026-03-25&starting_after=opaque&limit=20'
```

## Verified

This surface was verified against the public no-auth Snyk REST spec
`https://api.snyk.io/rest/openapi` on 2026-08-18.

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
- Limit bounds are 10 to 100 for orgs, projects, issues, and targets.

## Unverified

- Live tenant entitlement behavior was not exercised.
- `findings` is an Early Access endpoint; Snyk may require a version string
  with an `~experimental` suffix (e.g. `2026-03-25~experimental`) rather than
  a plain date. Use `--version` to override if the plain date 404s.
