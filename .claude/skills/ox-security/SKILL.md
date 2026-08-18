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
python3 ~/.claude/skills/ox-security/ox_security.py issues --limit 10 --severity Critical --app Org/repo
# illustrative output:
name	app	severity	tool_severity	tools	priority	epss	pct	wild	fix
Secret in code	api	Critical	High	Snyk	high	0.91	99	yes	yes
```

`severity` is OX's own severity, the field `--severity` filters on.
`tool_severity` is `originalToolSeverity`, the severity the source scanner
assigned. The two can legitimately disagree on the same row.

```bash
python3 ~/.claude/skills/ox-security/ox_security.py issues --filter tags=pci --filter tags=pii
# repeats append into filters.tags == ["pci", "pii"]
```

```bash
python3 ~/.claude/skills/ox-security/ox_security.py apps --search api
# illustrative output:
appId	repo	branch	prod	priority	matched
a1	api	main	yes	high	Snyk
```

```bash
python3 ~/.claude/skills/ox-security/ox_security.py app-flows app-id
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
`severity`, `originalToolSeverity`, `issueId`, `app.businessPriority`,
`scaVulnerabilities.cve`, `scaVulnerabilities.epss`,
`scaVulnerabilities.percentile`, `scaVulnerabilities.exploitInTheWild`, and
the vendor-spelled parent `prDeatils` with subfields `prURL` and `prStatus`.
`IssuesInput.limit` is `Int!`; `GetApplicationsInput.limit` is nullable `Int`.

`Authorization` defaults to the bare API key. `OX_AUTH_BEARER=1` is the opt-in
escape hatch for tenants that require `Bearer <key>`.

`Application.id` is deprecated; use `Application.appId`. `applicationFlows` is
a singular `ApplicationFlow` object. `RepositoryItem` fields are `type`,
`system`, `date`, and `location`; `CicdInfo` fields are `type`, `system`,
`latestDate`, `lastMonthJobCount`, and `location`; `KubernetesItem` does not
have `cluster` or `region`.

### Verified against a LIVE tenant (2026-08-18)

The docs above describe `IssuesInput.search` (`[AutoCompleteSearch]`) and
`GetApplicationsInput.filterSearch` (`[AutoCompleteSearch]`) as the filter
mechanisms. Both validate and are accepted by the server, and both are
silently ignored by the tenant: `--severity Critical` through `search`
returned `totalFilteredIssues: 0` while the same unfiltered query proved
Critical issues exist. Do not "fix" this tool back to `search` /
`filterSearch`; that is the bug being fixed, not the correct shape.

- Issue filtering goes through `IssuesInput.filters` (`IssueFilters`), an
  object of category -> list. `filters` is absent from OX's published SDL
  but is deployed and working. The 20 legal keys, live-probed one by one:
  `apps`, `criticality`, `categories`, `policies`, `issueOwners`,
  `issueNames`, `sourceTools`, `cwe`, `severityChange`,
  `severityChangeReasons`, `issueStatus`, `issueActions`,
  `originalSeverity`, `uniqueLibs`, `filePaths`, `languages`, `cve`,
  `oscar`, `issuesWithout`, `tags`. `fixedIssues` and `severity` are NOT
  valid keys; the server rejects them by name.
- `criticality` is the enum `CriticalityFilter` with exactly six
  case-sensitive members: `Appoxalypse`, `Critical`, `High`, `Medium`,
  `Low`, `Info`. Lowercase or uppercase variants are rejected.
- `apps` takes the fully qualified `Org/repo` app name as shown in the
  `appName` column, not the bare repo name.
- Applications have no working structured filter. `filterSearch` is
  accepted and ignored (`totalFilteredApps` unchanged whether sent or not).
  `--search` (`GetApplicationsInput.search`, a plain string) is the only
  filter that narrows results, and it is a substring match.
- Paging is `--offset` + `--limit` only. `IssuesInput.page` and
  `GetApplicationsInput.page` both validate and are silently ignored: two
  different `page` values returned the same rows. `offset` correctly
  advances results. `--cursorValue` is real and fails loudly if it does not
  match the sort used to obtain it.
