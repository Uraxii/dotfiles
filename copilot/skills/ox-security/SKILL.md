---
name: ox-security
description: Query OX Security as a connector aggregator for issues, apps, prioritization, and repo-to-runtime paths; use it for OX plus Snyk, Sysdig, Azure Repos, Azure Pipelines, ACR, and AKS questions via Issue.sourceTools and Application.applicationFlows, but never for Cloudflare WAF/CDN/DNS.
---

# ox-security

Thin OX Security GraphQL reader. It sends only allowlisted read-only `query`
documents to OX's Apollo Gateway and cannot change anything in the vendor
tenant.

Required env: `OX_API_KEY`. Optional env: `OX_API_URL`, `OX_AUTH_BEARER=1`.
By default this tool sends the bare key as `Authorization: <key>`; set
`OX_AUTH_BEARER=1` to send `Authorization: Bearer <key>`.

Rate limits: 1,000 req/hour and 15,000 req/day. The full public
GraphQL schema is markdown linked from `https://docs.ox.security/llms.txt`;
append `.md` to any OX docs page.

## Use it

```bash
python3 ~/.copilot/skills/ox-security/ox_security.py issues --limit 10 --severity Critical
# illustrative output:
app	priority	severity	tools	epss	pct	wild	fix
api	high	critical	Snyk	0.91	99	yes	yes
```

```bash
python3 ~/.copilot/skills/ox-security/ox_security.py apps --search api
# illustrative output:
appId	repo	branch	prod	priority	matched
a1	api	main	yes	high	Snyk
```

```bash
python3 ~/.copilot/skills/ox-security/ox_security.py app-flows app-id
# illustrative output:
repo	branch	prod	repository	cicd	artifact	k8s	cloud
api	main	yes	Azure Repos	Azure Pipelines	sha256:abc	api-prod	api:latest
```

## Can answer

- OX issue prioritization with EPSS, percentile, exploit-in-the-wild,
  fix availability, original scanner severity, source scanner, app name, and
  app business priority.
- Snyk and Sysdig questions visible through OX connectors. Route by
  `Issue.sourceTools`.
- Azure Repos, Azure Pipelines, ACR, and AKS questions visible through OX
  connectors. Route by `Application.applicationFlows`, which models
  repo -> cicd -> artifact -> kubernetes -> cloudDeployment.
- OX application inventory, production deployment flag, business priority, and
  matched Snyk project mappings.

## Cannot answer

- Cloudflare WAF, CDN, DNS, Workers, or Cloudflare analytics questions.
  Cloudflare is not an OX connector and has no WAF/CDN/DNS coverage in OX.
  Use the Cloudflare skill directly.
- Writes, comments, severity updates, false-positive reports, or exclusions.
- Arbitrary GraphQL supplied by the user.

## Verified

Schema was read from OX's public docs markdown on 2026-08-18. Verified:
`getIssues(getIssuesInput:)`, `getApplications(getApplicationsInput:)`,
`getApplications.applications`, issue fields including `sourceTools`,
`originalToolSeverity`, `issueId`, `app.businessPriority`,
`scaVulnerabilities.cve`, `scaVulnerabilities.epss`,
`scaVulnerabilities.percentile`, `scaVulnerabilities.exploitInTheWild`, and
the vendor-spelled parent `prDeatils` with subfields `prURL` and `prStatus`.

`IssuesInput` and `GetApplicationsInput` are intentionally different. Issues
uses `topLevelSearch: String` for free text and `search:
[AutoCompleteSearch]` for `--severity` and `--app`; each entry carries
`fieldName` and list-valued `value`. Applications uses plain `search: String`
for free text, `filterSearch: [AutoCompleteSearch]` for autocomplete filters,
and `appId` to target one app flow. `IssuesInput.limit` is `Int!`;
`GetApplicationsInput.limit` is nullable `Int`.

`Authorization` defaults to the bare API key. `OX_AUTH_BEARER=1` is the opt-in
escape hatch for tenants that require `Bearer <key>`.

`Application.id` is deprecated; use `Application.appId`. `applicationFlows` is
a singular `ApplicationFlow` object. `RepositoryItem` fields are `type`,
`system`, `date`, and `location`; `CicdInfo` fields are `type`, `system`,
`latestDate`, `lastMonthJobCount`, and `location`; `KubernetesItem` does not
have `cluster` or `region`.
