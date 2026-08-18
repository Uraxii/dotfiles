---
name: azure-devops
description: Query Azure DevOps projects, repos, builds, pipelines, releases, environments, Kubernetes resources, and WIQL work item ids through read-only public REST APIs for CI, release, repository, and deployment inventory questions.
---

# azure-devops

Thin Azure DevOps REST reader. It only reads. Most commands are GET; `wiql` is
the one POST because WIQL is read-only and returns ids only.

Required env: `AZURE_DEVOPS_ORG` plus `AZURE_DEVOPS_PAT` or
`AZURE_DEVOPS_BEARER_TOKEN`. `--org` may override the organization only.
`--api-version` overrides the api-version string for the current command
(defaults come from `ENDPOINTS`; most are `7.2-preview.N`, but `environments`,
`k8s`, and `release-env` default to `7.1-preview.N` because production
clients, including Microsoft's own `azure-devops-python-api`, ship that form).
Pass `--api-version 7.2-preview.N` to reach the 7.2 route if you need it.

Optional auth: Entra bearer token from
`az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798`.
The CLI accepts that token from env; it does not shell out to `az`.

## Can answer

- Which Azure DevOps projects, Git repositories, pipelines, runs, builds, and
  build artifacts are visible.
- Which release deployments and release definitions exist for a project.
- Repo to build to release edges: build repository, commit SHA, run repository
  refs, release `artifactSourceId`, and Kubernetes cluster/namespace.
- YAML environment inventory and Kubernetes resource details.
- WIQL result ids. Hydrating those ids needs `_apis/wit/workitems`, which this
  tool does not call.

## Cannot answer

- No writes or mutation.
- No pipeline preview dry runs. That endpoint queues a dry run and is not read.
- No work item hydration beyond WIQL ids.
- No cross-vendor correlation.
- No historical trending.
- No repo refs/versions on `runs`. The pipeline runs LIST response omits
  `resources` entirely (it exists only on run-detail, which this tool does
  not call), so those two columns were dropped rather than always printing
  a dash.

## Use it

```bash
python3 ~/.claude/skills/azure-devops/azure_devops.py projects
# illustrative output:
id	name	state	visibility	description
p1	api	wellFormed	private	Service API
```

```bash
python3 ~/.claude/skills/azure-devops/azure_devops.py builds --project api
# illustrative output:
id	number	status	result	repo_id	repo_name	repo_type	repo_url	default_branch	source_version
7	20260101.1	completed	succeeded	r1	api	TfsGit	https://example	refs/heads/main	abc123
```

```bash
python3 ~/.claude/skills/azure-devops/azure_devops.py releasedefs --project api --expand artifacts
# illustrative output:
id	name	artifact_source_id	artifact_type
9	api-release	project-guid:42	Build
```

```bash
python3 ~/.claude/skills/azure-devops/azure_devops.py k8s --project api --envId 1 --resourceId 2
# illustrative output:
cluster_name	namespace	service_endpoint_id	tags	environment_reference
aks-prod	prod	svc1	['prod']	{'id': 1}
```

```bash
python3 ~/.claude/skills/azure-devops/azure_devops.py wiql --project api --query "Select [System.Id] From WorkItems"
# illustrative output:
id	url
123	https://dev.azure.com/org/_apis/wit/workItems/123
```

## Verified

Verified against learn.microsoft.com `azure-devops-rest-7.2` on 2026-08-18.

- Bare `7.2` as an API version is not documented. Each 7.2 endpoint uses its exact
  `-preview.N` suffix, and the suffix differs per endpoint.
- Release Management uses `vsrm.dev.azure.com`, not `dev.azure.com`.
- `environments` and `k8s` default to `api-version=7.1-preview.1`, not bare
  `7.1`: the bare form 400s on this preview-only route, per
  `azure-devops-python-api`'s `task_agent_client.py`. A renamed `7.2-preview.1`
  route exists for environments too; reach it with `--api-version`.
- `release-env` defaults to `api-version=7.1-preview.7`, matching what
  `azure-devops-python-api` sends, instead of the higher-404-risk
  `7.2-preview.8`.
- Azure DevOps OAuth is deprecated, with full deprecation in 2026. Entra is
  Microsoft's recommended auth path.
- Read-only PAT scopes used by these reads: `vso.project`, `vso.code`,
  `vso.build`, `vso.release`, `vso.serviceendpoint`, `vso.work`, and
  `vso.profile`.
- Prominent PAT warning: `vso.environment_manage` has no read-only sibling and
  is high-privilege. The `environments` and `k8s` subcommands therefore cost a
  manage-tier scope even though this tool only reads.

## Unverified

- The `x-ms-continuationtoken` response header is an undocumented real-world
  convention, not endpoint spec. The tool reads it defensively when present.
