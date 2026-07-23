---
name: agent-workbench
description: Locally deployable agent workbench (knowledgebase vault + bd board hub + bdui web front end + hardened kb-serve/review-serve containers) driven by ONE pure-Python CLI. Use to run knowledgebase clip/put/query, manage bd boards under the central hub, launch the board web UI, scaffold a repo's agent workspace, or build and deploy the two review/knowledgebase containers locally. Replaces the old scripts/*.sh shell tools and the bash deploy driver.
---

# agent-workbench

One skill, one executable, five subcommands. Every tool is pure Python
(argparse, stdlib + the two pre-existing lxml/readability deps kb-clip
already used). No bash, no `.sh` shims. The CLI lives BESIDE the hardened
container, never inside its image.

```bash
.claude/skills/agent-workbench/agent-workbench <subcommand> [ARGS]
```

## Subcommands

| Subcommand | Replaces | Purpose |
|---|---|---|
| `kb` | `scripts/kb.sh` | knowledgebase vault: init/add/path/index/clip/put/query/atomize/status |
| `hub` | `scripts/beads-hub.sh` | bd board hub: init/add/sync/list/path/status |
| `board` | `scripts/board-ui.sh` | bdui web front end: up/down/status |
| `init-workspace` | `scripts/init-agent-workspace.sh` | scaffold docs/kb + workstreams + bd board + reindex hook into a repo |
| `deploy` | `deploy/agent-workbench/agent-workbench` | build + run the kb-serve / review-serve containers |

### kb

```bash
agent-workbench kb clip "<url>" --project <project>
agent-workbench kb put <project> "<title>" --type note --source "<url>"  # body on stdin
agent-workbench kb query "<terms>" --project <project> --type source
agent-workbench kb index
agent-workbench kb status
```

`clip` / `put` / `query` prefer the running kb-serve HTTP service (so the
call also atomizes + reindexes) and fall back to an in-process kb-serve.py
call when the service is down. Same behavior kb.sh had.

### hub / board / init-workspace / deploy

```bash
agent-workbench hub add <name> [prefix]
agent-workbench board up [REPO_DIR]        # prints the UI URL
agent-workbench init-workspace [TARGET_DIR] [--prefix PREFIX]
agent-workbench deploy up | down | status
```

## How it differs from the old scripts

- **Pure Python, single entrypoint.** The five separate shell scripts +
  the bash deploy driver collapse into one executable with subcommands.
  The `kb` family stays a thin facade over the existing
  `scripts/kb-serve.py` (which already facades kb-index / kb-clip /
  kb-atomize); hub/board/init-workspace/deploy are genuine rewrites.
- **Audit fixes folded in:**
  - `kb` honors `KB_SERVE_HOST` (not only `KB_SERVE_PORT`) and surfaces
    the HTTP error body on failure instead of swallowing it.
  - `board` validates the hub board (`$HUB_ROOT/<name>/.beads`), not a
    stale repo-local `<repo>/.beads`.
  - `hub` runs `bd init` with `BEADS_DIR` stripped from the child env so
    an ambient value cannot redirect where the board is written, and uses
    a correctly-sensed `git_repo_preexisted` flag for incidental-repo
    cleanup.
- **The clip path preserves kb-clip.py's http/https scheme allowlist
  verbatim** (it delegates to the same `check_url_scheme`), so `file://`
  and other schemes stay rejected with zero new code.

## Deploy + hardening

`deploy up` builds and starts the two hardened containers as rootless
podman-quadlet user units. Hardening (read-only rootfs, `cap-drop=ALL`,
`no-new-privileges`, seccomp default, digest-pinned base image,
HEALTHCHECK, narrowed mounts) and the env config surface are documented
in `docs/agent-workbench-hardening-plan.md`.

Optional data-root overrides live in
`.claude/skills/agent-workbench/agent-workbench.env.example`. NOTE:
`KB_HOME` / `ARTIFACTS_HOME` are NOT functional overrides once the
containers are running (the quadlets bind `%h`-relative paths); only
`BEADS_HUB_DIR` is read directly by the Python code. See the env.example
comments.

## n8n Public API (agent-facing)

n8n's Public REST API is enabled (pinned in `n8n.container`), letting an
agent create and trigger workflows without a human in the loop for the
API calls themselves.

**One-time human bootstrap** (already done for the owner account setup;
only the API key step remains): log into the n8n editor at
http://127.0.0.1:5678, go to Settings -> n8n API -> Create an API Key,
then store the value per `scripts/n8n-container/n8n.env.example`'s
`N8N_API_KEY` / `N8N_API_KEY_CMD` Mode 2 block. There is no headless mint
path for this key in n8n Community edition.

**Agent resolves the key:**

```bash
API_KEY=$(scripts/n8n-container/n8n-secret.py resolve-api-key --data-dir ~/.local/share/n8n)
```

**Create a workflow** (body = a workflow JSON file):

```bash
curl -X POST http://127.0.0.1:5678/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "X-N8N-API-KEY: $API_KEY" \
  --data @path/to/workflow.json
```

**Activate it** (makes its trigger nodes live):

```bash
curl -X POST http://127.0.0.1:5678/api/v1/workflows/<id>/activate \
  -H "X-N8N-API-KEY: $API_KEY"
```

**Trigger an already-activated Webhook-triggered workflow** (no API key
needed for the webhook call itself, only the two calls above use it):

```bash
curl -X POST http://127.0.0.1:5678/webhook/<path>
```

This only works for workflows containing a Webhook trigger node. The
starter workflow at `workflows/image-approval-pipeline.n8n.json` uses a
Form Trigger instead, so it is NOT webhook-triggerable as-is -- a
separate, already-ticketed workflow-design concern.

All endpoints above are `http://127.0.0.1:5678` (loopback-published;
reachable over Tailscale via the host, same as the rest of this stack).
