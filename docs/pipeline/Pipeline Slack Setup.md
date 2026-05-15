# Pipeline Slack Setup

End-to-end install for the async-decision Slack listener. Per-run process, spawned on demand by the orchestrator. Outbound-only (Socket Mode WebSocket; no inbound port, no public URL).

## Architecture recap

```
                       WSS (outbound)
[per-run listener] ─────────────────► Slack
       │                                  │
       │  inotify on <run-dir>/           │  button click
       ▼                                  ▼
   awaiting-decision-r<N>.md      listener writes decision-r<N>.md
```

One listener per pipeline run that uses async-mode decisions. Each listener:

- Spawned by the orchestrator at async-mode entry via `subprocess.Popen` (detached, `start_new_session=True`).
- Loads `~/.claude/pipeline/slack.env.local` (shared tokens).
- Reads `<project>/.pipeline/pipeline.toml` (per-project channel).
- Watches its `<run-dir>/awaiting-decision-r*.md` only (inotify, non-recursive).
- Posts threaded message per run; one thread = one run.
- On button click → writes `<run-dir>/decision-r<N>.md`, deletes awaiting file.
- Self-exits 30 seconds after the run's awaiting set has been empty. Orchestrator re-spawns idempotently if a later decision lands in the same run.

No systemd. No always-on daemon. Portable to any POSIX host with Python ≥3.11 and `uv`.

## Fast path (new machine)

```bash
git clone <this-repo> ~/dotfiles
cd ~/dotfiles && stow -t ~ .

# Pre-flight: verify all deps, paths, and Slack scopes:
bash ~/.claude/pipeline/setup.sh
```

### Distro packages (the bits stow cannot install)

| OS | Command |
|---|---|
| **Any supported distro (recommended)** | `./install.py --group pipeline` (reads `deps.toml`; dispatches to native pkg manager per distro). |
| **Arch (manual)** | `sudo pacman -S stow uv jq pango cairo gdk-pixbuf2 github-cli` |
| **Debian / Ubuntu (manual)** | `sudo apt install stow jq libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 gh && curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **macOS (Homebrew)** | `brew install stow uv jq pango cairo gdk-pixbuf gh` |

`setup.sh` checks: external commands (`python3 ≥3.11`, `uv`, `stow`, `jq`,
`curl`, `git`, `uvx`), stowed symlinks, `slack.env.local` file mode, and
probes Slack live for `auth.test` + scope coverage. Prints a checklist with
fix hints; exits 0 only when everything is ready. Run it again after each
configuration change. The rest of this doc is the underlying procedure each
check exercises.

## One-time setup

### 1. Create the Slack app

Fastest: import the included manifest.

1. Visit https://api.slack.com/apps → **Create New App** → **From a manifest**.
2. Pick your workspace → paste contents of
   `~/.claude/pipeline/slack-app-manifest.yaml` into the **YAML** tab → **Next** → **Create**.

Manual alternative: **Create New App** → **From scratch** → name + workspace → **Create**.

### 2. Bot token scopes

**OAuth & Permissions** → **Bot Token Scopes** (already declared by the manifest):

- `chat:write` — post messages
- `chat:write.public` — post in public channels without being a member
- `channels:history` — Phase 2 (free-text thread replies; optional today)
- `groups:history` — Phase 2 (free-text thread replies; optional today)
- `files:read` — required for `pipeline_ask.py --attach`
- `files:write` — required for `pipeline_ask.py --attach`

Click **Install to Workspace** → authorize. Copy the **Bot User OAuth Token** (starts `xoxb-`).

After any scope change Slack will prompt **Reinstall to Workspace** — do it; tokens
do not pick up new scopes until reinstall.

### 3. Enable Socket Mode

1. **Settings → Socket Mode** → toggle **Enable Socket Mode**.
2. Generate App-Level Token (it prompts when you enable Socket Mode):
   - Name: `pipeline-socket`
   - Scope: `connections:write`
   - Copy the token (starts `xapp-`).

### 4. Enable Interactivity

**Features → Interactivity & Shortcuts** → toggle **Interactivity** on. No Request URL required (Socket Mode handles it).

### 5. Reinstall (if Slack prompts)

Whenever **scopes** OR **Event Subscriptions** change, Slack will prompt **Reinstall to Workspace**. Do it. Subscription changes are dormant until reinstall — the app stays connected, posts succeed, buttons work, but `message.channels` / `message.groups` events are never delivered. Symptom: router log shows Bolt connected + `hello` only, zero `event_callback`s after thread replies. Fix: reinstall to workspace from the app config page.

### 6. Save tokens locally

```bash
mkdir -p ~/.claude/pipeline
cp ~/.claude/pipeline/slack.env.example ~/.claude/pipeline/slack.env.local
chmod 600 ~/.claude/pipeline/slack.env.local
$EDITOR ~/.claude/pipeline/slack.env.local   # paste xoxb- and xapp- tokens
```

Optional: restrict button clicks to specific users by setting `SLACK_ALLOWED_USERS` to a comma-separated list of Slack user IDs (find via profile → ⋮ → Copy member ID).

### 7. Python deps (uv-managed)

The listener uses [PEP 723 inline script metadata](https://peps.python.org/pep-0723/) — deps declared in the script header. `uv run --script` resolves and caches them on first run.

Requires `uv` ≥ 0.10 + system Python ≥ 3.11 (repo uses 3.14):

```bash
command -v uv || pacman -S uv      # or your distro's pkg
```

First run populates cache (`~/.cache/uv`):

```bash
uv run --script ~/.claude/pipeline/slack_listener.py ~/dotfiles
```

(It will exit with "missing pipeline.toml" — that's expected at this stage and confirms the env resolves.)

`tomllib` is stdlib on Python 3.11+.

## Channel setup

### 1. Create the channel + invite the bot

- Create one channel for pipeline decisions. Runs from every project post threaded messages here; each thread is one run, the parent message shows the project name.
- `/invite @your-bot-name` in that channel (once, ever).
- Grab the channel ID: right-click channel → **View details** → bottom shows **Channel ID** (`C...`).

### 2. Set the channel as global default

Add `SLACK_CHANNEL=C0123ABC456` to `~/.claude/pipeline/slack.env.local`. All projects pick this up automatically — no per-project setup needed.

### 3. Optional per-project override

Only needed if a specific project should post to a different channel (e.g. private client channel). Create `<project>/.pipeline/pipeline.toml`:

```toml
[slack]
channel = "C9999ZZZZ"     # override; overrides SLACK_CHANNEL env var for this project only
project_name = "myproject" # optional; shown in parent thread message (defaults to dir basename)
```

The file is gitignored via `.pipeline/*` blanket. Per-machine, per-project.

### 4. Lifecycle (orchestrator-managed)

No systemd unit. No always-on daemon. The orchestrator spawns one listener per pipeline run when that run enters the decision-elicitation stage in async mode. The listener self-exits when its run's awaiting set has been empty for 30 seconds.

Per-run files (all under `<project>/.pipeline/runs/<run-id>/`):

| File | Owner | Purpose |
|---|---|---|
| `slack-listener.pid` | listener | Liveness check; removed at clean exit. |
| `slack-state.json`   | listener | Thread + posted-decision cache. |
| `awaiting-decision-r<N>.md` | orchestrator | Listener posts to Slack on appearance. |
| `decision-r<N>.md` | listener | Written on button click; orchestrator polls. |

Spawn command (orchestrator does this internally; useful for debugging):

```bash
uv run --script ~/.claude/pipeline/slack_listener.py "$PROJECT_PATH" "$RUN_ID"
```

Idempotent: if a listener PID file is found and the process is alive, the orchestrator skips re-spawn.

Portability: no systemd dependency. Works on any POSIX host with Python ≥3.11 and `uv`.

### 5. Smoke test

```bash
PROJECT_PATH=~/path/to/your/project
RUN=test-run-$(date +%s)
mkdir -p "$PROJECT_PATH/.pipeline/runs/$RUN"

cat > "$PROJECT_PATH/.pipeline/runs/$RUN/options-r1.md" <<'EOF'
---
decision_id: d1
topic: Smoke test
requesting_role: tester
count: 2
delivery_default: async
---

## Option A: Yes
- **Tradeoff:** confirm setup works

## Option B: No
- **Tradeoff:** roll back
EOF

cat > "$PROJECT_PATH/.pipeline/runs/$RUN/awaiting-decision-r1.md" <<EOF
---
decision_id: d1
delivery_mode: async
opened_at: $(date -u +%FT%TZ)
timeout_at: $(date -u -d '+1 hour' +%FT%TZ)
requesting_role: tester
options_source: tester
topic: Smoke test
---
EOF

# Spawn the listener in foreground for visible logging:
uv run --script ~/.claude/pipeline/slack_listener.py "$PROJECT_PATH" "$RUN"
```

A threaded decision message should appear in the channel within ~1s. Click a button → `decision-r1.md` written + awaiting file deleted + listener exits after the 30s grace window.

## Multiple projects / multiple concurrent runs

No per-project setup beyond `pipeline.toml`. Each pipeline run gets its own listener process spawned by the orchestrator on demand. Concurrent runs across multiple projects = multiple listener processes, each scoped to one run dir. They share the same Slack app + tokens but post to different (or the same) channel based on each project's `pipeline.toml`.

Slack Socket Mode connections per active run; each lives only while that run has open decisions. Practical concurrency limit = Slack's per-app Socket Mode cap (10 on free tier).

## Listing live listeners

```bash
# Across all projects:
for pid in $(find ~ -name slack-listener.pid 2>/dev/null); do
  kill -0 "$(cat "$pid")" 2>/dev/null && echo "alive: $pid"
done
```

To stop one: `kill $(cat <run-dir>/slack-listener.pid)`. The listener removes its PID file on exit.

## Troubleshooting

| Symptom | Check |
|---|---|
| Log shows `not_authed` | Tokens missing or wrong scope. Re-paste from app config. |
| `not_in_channel` errors | Bot needs `/invite` in the channel. File uploads require channel membership (chat:write.public covers posting but not uploads). |
| `channel_not_found` | `channel` in `pipeline.toml` is the channel name not the ID. Use `C...` ID. |
| `missing_scope` on file upload | `files:write` not on the token. Add scope in OAuth & Permissions, click **Reinstall to Workspace**, refresh `slack.env.local`. |
| Bash tool kills `pipeline_ask` at 10min | `BASH_MAX_TIMEOUT_MS` not raised. Verify via `setup.sh` → "Claude Code settings" check. |
| Long Bash command blocked by hook | `cap_bash_timeout.py` allowlists `pipeline_ask.py` only. Other long-running commands need entry added to `LONG_TIMEOUT_ALLOWLIST` in that hook. |
| HTML attachment shows raw source instead of PDF | uvx/weasyprint missing or system pango libs absent. `setup.sh` warns; install distro pango pkg + retry. |
| Buttons appear but click does nothing | Interactivity toggle off, or Socket Mode disabled. Re-check Slack app config. |
| Bind posts root message but thread replies never reach router | Event Subscriptions changed without reinstall, OR app not reinstalled after first enabling events. Router log shows `hello` only, no `event_callback`. Fix: api.slack.com/apps → app → top of page → **Reinstall to Workspace**. Restart router. |
| Listener exits immediately | Run in foreground: `uv run --script ~/.claude/pipeline/slack_listener.py <project> <run-id>` to see the traceback. |
| `uv` cannot resolve deps | First run populates `~/.cache/uv`; needs network. After that, offline-capable. |
| Listener eats CPU | inotify storm on shared FS. Move `.pipeline/runs/` off network mount. |
| Stale PID file blocks respawn | `kill $(cat <run-dir>/slack-listener.pid)` if process is dead but file remains; orchestrator's next spawn cycle handles it via `os.kill(pid, 0)` liveness check. |

## Security notes

- Tokens live in `~/.claude/pipeline/slack.env.local`, mode 600, never in the repo. The `.local` suffix matches `.gitignore` (`.claude/**/*local*`) and `.stow-local-ignore` (`\.claude/.*local.*`) so the real file is never tracked and never symlinked by stow.
- Listener runs as your user with no extra sandboxing (no systemd unit). Filesystem access is whatever your shell has. If you need sandbox hardening, wrap the spawn in your preferred mechanism (firejail, systemd-run, etc.) — the script accepts standard process management.
- Outbound TCP 443 only (Socket Mode WebSocket). Verify with `ss -tlnp` — no new listening port should appear after starting a listener.
- Optional allowlist (`SLACK_ALLOWED_USERS`) gates button clicks; everyone else gets an ephemeral "not authorized" message.

## Session-bound mode

One Claude Code session = one Slack thread. Opt-in via `/slack-bind`.

### Activate

```bash
/slack-bind
# or directly:
python3 ~/.claude/pipeline/session_bind.py activate
```

Posts a root message to the configured channel. Captures `thread_ts`. Writes
`~/.claude/sessions/<sid>/slack.json`. Spawns a per-session inbox daemon that
captures user replies while no pipeline listener is running.

Output JSON: `{"channel": "C...", "thread_ts": "...", "session_id": "...", "daemon_pid": ...}`

### Deactivate

```bash
/slack-unbind
# or:
python3 ~/.claude/pipeline/session_bind.py deactivate
```

Posts `Session ended at <iso8601>` in the bound thread. Flips `active=false`.
SIGTERMs the inbox daemon. Inbox files are **preserved** for audit.

### Status

```bash
/slack-status
# or:
python3 ~/.claude/pipeline/session_bind.py status
```

Prints JSON state including `daemon_pid_alive` bool.

### Multi-session model

Each Claude Code process has a distinct `CLAUDE_CODE_SESSION_ID`. Each session
gets its own `slack.json` + inbox directory + Slack thread. Two concurrent
sessions never share a thread. Session state lives under `~/.claude/sessions/`
(not under any project tree).

### Inbox semantics

User replies posted in a bound session thread are captured by either:
- The per-run listener (alive during a pipeline decision/question wait), or
- The always-on session-inbox daemon (active for the entire bound session lifetime).

Files land at `~/.claude/sessions/<sid>/inbox/<msg_ts>.json`. Read via:

```bash
python3 ~/.claude/pipeline/inbox_drain.py [--consume] [--json]
```

Inbox messages do NOT auto-resume any pipeline. They are consumed only when an
on-demand skill explicitly drains the inbox, or when a `decision-elicitation` /
`question-elicitation` wait completes (those write structured `decision-r<N>.md`
/ `answer-r<N>.md`, not inbox files).

### Daemon lifecycle

The session-inbox daemon is spawned by `activate` and killed by `deactivate`
(SIGTERM). Its pid is stored in `slack.json` as `inbox_daemon_pid`. If it dies
between bind and unbind, re-run `activate` — it detects the dead pid and
respawns.

Check daemon health:

```bash
python3 ~/.claude/pipeline/session_bind.py status \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    print('alive' if d.get('daemon_pid_alive') else 'dead')"
```

### Idle timeout

The per-run listener's idle exit is controlled by `SLACK_LISTENER_IDLE_TIMEOUT`
(seconds; default 86400 = 24h). Set in `~/.claude/pipeline/slack.env.local`:

```bash
SLACK_LISTENER_IDLE_TIMEOUT=3600   # 1 hour
```

### Channel mismatch handling

If the session-bound channel differs from the project channel in `pipeline.toml`:
the session-bound channel wins; a warning is posted in the session thread and
written to `pipeline.md` `slack.warning`. Pipeline continues.

### Slack app scopes (session-bound additions)

To capture thread replies, the Slack app must subscribe to:
- `message.channels` — replies in public channels
- `message.groups` — replies in private channels

Add under **Event Subscriptions** in the Slack app config, then
**Reinstall to Workspace**.

### Required new files

| File | Purpose |
|---|---|
| `~/.claude/pipeline/session_bind.py` | activate/deactivate/status CLI |
| `~/.claude/pipeline/session_slack.py` | stdlib-only binding helper |
| `~/.claude/pipeline/session_inbox.py` | per-session inbox daemon |
| `~/.claude/pipeline/pipeline_notify.py` | one-shot status/completion notify |
| `~/.claude/pipeline/_slack_env.py` | shared env-file loader |

## Related

- [[Pipeline Decisions]] — full decision-elicitation stage doc.
- [[Pipeline Skills|decision-elicitation skill]] — orchestrator-side contract.
- [[Pipeline Artifacts]] — `awaiting-decision-r<N>.md`, `decision-r<N>.md` schemas.
