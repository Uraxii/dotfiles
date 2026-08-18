---
name: sysdig
description: Query Sysdig Secure read-only SaaS APIs for AKS runtime vulnerability posture, vulnerability result details, SBOM lookup, inventory, zones, and secure events.
---

# sysdig

Thin Sysdig Secure reader. It is read-only, GET only, and cannot change
anything in the vendor tenant.

Required env: `SYSDIG_API_TOKEN` and `SYSDIG_HOST`, unless `--host` is passed.
Optional env: none.

## Use it

```bash
python3 ~/.copilot/skills/sysdig/sysdig.py --host us2 runtime --running
# illustrative output:
id	asset	type	cluster	namespace	running_vulns	total_vulns	policy
r1	ghcr.io/acme/api:1.2	containerImage	prod	orders	critical:2,high:4,medium:0,low:0,negligible:0	critical:10,high:22,medium:5,low:0,negligible:0	failed
```

```bash
python3 ~/.copilot/skills/sysdig/sysdig.py --host us2 result --id r1
# illustrative output:
package	version	vuln	severity	exploitable	exploit	accepted_risks	fixed_in
openssl	3.0.1	CVE-2026-0001	critical	true	true	[]	3.0.2
```

```bash
python3 ~/.copilot/skills/sysdig/sysdig.py --host us2 inventory --filter 'cluster="prod"'
# illustrative output:
id	name	type	status
h1	aks-node-1	Kubernetes Node	true
```

## Can answer

- AKS runtime vulnerability posture from runtime results.
- Running-vulnerability counts beside total vulnerability counts.
- Cluster and namespace for runtime image findings.
- Per-vulnerability exploitable, exploit, accepted risk, and fixed version
  fields from a v1 result detail call.
- Registry, pipeline, SBOM, inventory, zone, and secure event reads.

## Cannot answer

- Azure App Service, Azure Functions, or Cloudflare Workers runtime signal.
  Sysdig covers AKS only. Do not route those questions here.
- Risks / attack-path data. There is no public REST endpoint; the UI is served
  by internal `/api/scanning/riskmanager/v2/definitions` and
  `/api/graph/v1/graphql`, which this tool does not call.
- Reporting v2, SysQL, writes, cross-vendor correlation, or historical
  trending.
- Rate-limit quotas. No numbers are published; VM endpoints emit
  `x-ratelimit-limit`, `x-ratelimit-remaining`, and `x-ratelimit-reset`
  response headers.

## Verified

Surface verified against IBM's public republication of the Sysdig Workload
Protection OpenAPI and the public examples cross-check on 2026-08-18. Caveat:
the IBM page is titled "Workload Protection API v2" and documents IBM IAM auth,
while path, param, and schema shapes match Sysdig SaaS.

Host is chosen by path family:

- `/secure/...` uses `api.<region>.sysdig.com`.
- `/api/...` and `/platform/...` use the app host: `us2` and `eu1` use
  `<region>.app.sysdig.com`; `us3`, `us4`, `eu2`, `au1`, `me2`, `in1`, and
  `jp1` use `app.<region>.sysdig.com`; `us1` uses `secure.sysdig.com`.
- Supported regions are `us1 us2 us3 us4 eu1 eu2 au1 me2 in1 jp1`.

Vulnerability runtime, registry, pipeline, and result detail calls use
`/secure/vulnerability/v1/...`. The `v1beta1` forms of those same four paths
(`runtime-results`, `registry-results`, `pipeline-results`, `results/{id}`)
were deprecated 2025-02-25 with a migrate-by date of 2025-09-01, and are
replaced one-for-one by the `v1` forms this tool calls.

`v1beta1` itself is not dead: Sysdig kept it for backward compatibility, and
it is still the only version that serves `sboms` and `accepted-risks`. There
is no `v1` SBOM path, so SBOM lookup correctly stays on
`/secure/vulnerability/v1beta1/sboms`.

`v1` renamed a field on the way from `v1beta1`: registry-results and
pipeline-results items carry `pullString` where `v1beta1` had
`mainAssetName`. runtime-results is the exception, it keeps `mainAssetName`
and additionally gained `resourceId`. `_basic_rows` falls back
`mainAssetName` -> `pullString` -> `name` so registry and pipeline rows still
show an asset name.

Unrelated deprecation, noted so it is not confused with the above: the
legacy V1 scanning engine (`/api/scanning/v1/anchore`) reached end of life
2024-12-31.

Pagination is intentionally endpoint-specific:

- Vulnerability lists and secure events use opaque cursor pagination from
  `page.next`, resent as `cursor`.
- Inventory uses `/secure/inventory/v1/resources` with `filter`,
  `withEnrichedContainers`, `pageSize`, and `pageNumber`.
- Inventory pagination reads `page.next` as the next page number and
  `page.total` as the page count.
- `/platform/v1/zones` uses only `filter=name:<value>` with no `/api` prefix,
  and returns a `zones` wrapper.

`GET /secure/vulnerability/v1beta1/accepted-risks` exists but is absent from
the IBM spec, so it is not implemented.

## Unverified

- Response shape of `GET /secure/vulnerability/v1beta1/accepted-risks`.
  Not in the IBM spec, not implemented, shape unconfirmed.
