---
name: artifact-serve
description: Stage artifacts/reports under /tmp/claude-artifacts/<project>/ + serve over local HTTP, optionally publish to Tailscale HTTPS URL for remote browser review. Auto-injects a per-page comment + file-upload widget so reviewers can leave feedback the agent reads back via `feedback --artifact <id>`. Use when user wants to share a generated mockup gallery, pipeline report, or static HTML output with a remote device, collect review notes against an artifact id, or attach reference screenshots/PDFs to a comment ("publish this report", "put this on tailscale", "let me leave feedback", "serve this dir").
---

# artifact-serve

Stage + serve generated artifacts (mockups, HTML reports, dashboards) for remote browser view. Single shared root `/tmp/claude-artifacts/`. One stdlib HTTP daemon. Optional Tailscale HTTPS. Per-page comments + uploads stored in durable sqlite, retrievable by artifact id.

## Quick start

```bash
# 1. Stage a directory (always symlinked — never copied). --id ties feedback rows to the artifact.
python3 ~/.claude/skills/artifact-serve/scripts/artifact-serve.py push \
  --project bhwf --src /home/nikki/Git/bhwf/mockups --id cool-beaming-rivest-cd9eb3

# 2. Start the local daemon + expose over Tailscale HTTPS
python3 ~/.claude/skills/artifact-serve/scripts/artifact-serve.py start --expose

# 3. (After reviewer leaves comments) pull feedback as JSON for agent consumption
python3 ~/.claude/skills/artifact-serve/scripts/artifact-serve.py feedback \
  --artifact cool-beaming-rivest-cd9eb3
```

Optional shell alias:
```bash
alias as='python3 ~/.claude/skills/artifact-serve/scripts/artifact-serve.py'
```

## Workflow

1. **Push**: `as push --project NAME --src PATH [--as SUBDIR] [--id ID]`
   Symlinks only. `NAME` + `SUBDIR` must match `[a-z0-9][a-z0-9_-]*`. `--id` defaults to `<project>/<subdir>` — pass an explicit slug (pipeline artifact-id, ticket id, etc.) to correlate feedback across re-pushes.
2. **Start**: `as start [--port N] [--expose]`
   Idempotent. Writes pid file. Regenerates root `index.html`.
3. **Browse**: open printed URL. Every HTML page served gets a Feedback section auto-injected at the bottom (comment textarea + file picker + submit).
4. **Feedback**: `as feedback --artifact ID` — JSON dump of comments + upload metadata for one artifact, across all sub-paths.
5. **Stop**: `as stop` — daemon down + `tailscale serve --https=443 off`.
6. **Clean**: `as clean --project NAME` — drops staging dir for one project. Feedback DB untouched.

Verbs: `push`, `unpush`, `start`, `expose`, `unexpose`, `status`, `stop`, `clean`, `feedback`, `name`. Full sigs, API endpoints, upload rules in [REFERENCE.md](REFERENCE.md).

Set your default comment-author name once: `as name nikki` → widget pre-fills it on every page, server stamps it on comments where the form leaves name blank.

## Security

- `--expose` / `expose` publishes served root over **entire Tailscale tailnet on HTTPS**, persistent until `unexpose`. Anyone w/ tailnet access can read AND post comments + uploads.
- Server follows pushed symlinks — anything reachable from targets reachable from URL. Don't push parent dirs of secrets.
- `/tmp/` wipes on reboot. **Feedback DB + uploads** live at `~/.local/share/claude-artifacts/` — durable.
- Uploads: 100 MB per file, 500 MB per request, extension allowlist (img/pdf/text/zip/fig/psd/mp4). `.exe/.sh/.js/.html/.svg` blocked.

Full security: [REFERENCE.md](REFERENCE.md).

## Setup (one-time)

```bash
chmod +x ~/.claude/skills/artifact-serve/scripts/artifact-serve.py
```

## Implementation

Helper at `scripts/artifact-serve.py`. stdlib only (`http.server`, `socketserver`, `subprocess`, `pathlib`, `argparse`, `sqlite3`, in-house multipart parser). Daemonizes via `os.fork`. Pid at `/tmp/claude-artifacts/.serve.pid`. Comments DB at `~/.local/share/claude-artifacts/feedback.db`. See [REFERENCE.md](REFERENCE.md) for storage layout, API endpoints, traversal rules, Tailscale wiring.
