# agent-workbench deploy bundle

One command to stand up the agent-workbench platform locally: two rootless
podman containers (kb-serve, review-serve) run as systemd user services,
plus the bd (beads) board hub, which is a plain data directory, not a
service.

This bundle does not define the containers itself -- it builds and wires
up the existing definitions in place:

- `scripts/kb-container/` (Containerfile, quadlet, env example)
- `.claude/skills/artifact-serve/container/` (Containerfile, quadlet)

See those directories' own READMEs for how each service works internally.
This one only covers the combined one-command flow.

## Prerequisites

- Rootless podman (tested with podman 5.x)
- A user systemd instance (`systemctl --user`), with
  `loginctl enable-linger $USER` run once so services survive logout
- `curl` (used for health checks)

## Up

```bash
deploy/agent-workbench/agent-workbench up
```

This builds both images (`localhost/kb-serve:latest`,
`localhost/review-serve:latest`), symlinks both quadlets into
`~/.config/containers/systemd/`, reloads systemd, and starts kb-serve.

review-serve is often already running as a hand-installed service before
you ever run this. `up` is non-destructive to it: if `review-serve.service`
is already active, `up` leaves it running exactly as-is (no restart, no
quadlet replacement) and only starts it if it was not already active.

## Down

```bash
deploy/agent-workbench/agent-workbench down
```

Stops and disables both units, and removes the quadlet symlinks this
bundle installed (never touches a hand-installed real quadlet file, only
symlinks it created itself).

**This also stops review-serve.** Running `down` at all is the operator's
opt-in to that -- if you only want kb-serve down, stop it directly instead:

```bash
systemctl --user stop kb-serve
```

## Status

```bash
deploy/agent-workbench/agent-workbench status
```

Prints `systemctl --user status` for both units plus a health curl for
each (`GET /health` on kb-serve, `GET /` on review-serve), and whether the
bd hub directory exists.

## Where data and secrets live

| Component | Data | Secrets |
|---|---|---|
| kb-serve | `~/.knowledgebase` (`KB_HOME`) | `~/.knowledgebase/kb.env`, gitignored, copied from `scripts/kb-container/kb.env.example` -- see that file/README for the two ways to supply an LLM API key. LLM enrichment is off by default. |
| review-serve | `~/.local/share/claude-artifacts` + `/tmp/claude-artifacts` | none |
| bd hub | `~/.beads-hub` | none |

`deploy/agent-workbench/agent-workbench.env.example` documents optional,
non-secret overrides for the three data-root paths above (`KB_HOME`,
`ARTIFACTS_HOME`, `BEADS_HUB_DIR`). Defaults are the current live paths;
copy the file, source it, or export the variables yourself before running
`up`. Note the two quadlet files themselves still hardcode their own paths
via systemd's `%h` -- relocating those is a separate, later track.

## Ports

| Service | Port | Health |
|---|---|---|
| kb-serve | 9100 | `GET http://127.0.0.1:9100/health` |
| review-serve | 9099 | `GET http://127.0.0.1:9099/` |

Both are published loopback-only; see each container's own README for the
networking details (kb-serve uses `PublishPort=127.0.0.1:...`, review-serve
uses `Network=host` for reasons documented there).

## Cloud and repo-extraction

Out of scope for this bundle. Local-only.
