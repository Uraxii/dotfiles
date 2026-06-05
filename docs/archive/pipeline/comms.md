# comms — pipeline communications provider abstraction

## Purpose

`comms/` is the provider abstraction layer for all pipeline notifications, questions, decisions, and session binding. It defines a `CommsProvider` protocol and `CommsRouter` daemon so the pipeline can target Slack today and future chat backends (Discord, etc.) by swapping providers. Slack is the only adapter in this pass.

## Key files

- `.claude/pipeline/comms/__init__.py` — package marker
- `.claude/pipeline/comms/types.py` — provider-neutral value types (`ThreadRef`, `MessageRef`, `OptionSpec`, `QuestionPost`, `DecisionPost`, `AuthCheck`, `InboundEvent`, `InboundConsumer`)
- `.claude/pipeline/comms/provider.py` — `CommsProvider` Protocol (structural, `@runtime_checkable`)
- `.claude/pipeline/comms/registry.py` — `CommsRegistry` singleton; resolves active provider from `[comms].provider` in `pipeline.toml`; default `"slack"`; unknown name raises `UnknownProviderError`
- `.claude/pipeline/comms/env.py` — generic 0o600-guarded env-file loader (moved from `_slack_env.py`); `load_env_file`, `atomic_write_text`, `validate_sid`, `default_env_path`
- `.claude/pipeline/comms/session.py` — provider-aware session binding reader; `_load_slack_json` applies `setdefault("provider", "slack")` at the lowest read level so legacy `slack.json` files (no `provider` field) are tolerated transparently
- `.claude/pipeline/comms/router.py` — `CommsRouter` daemon entrypoint; spawned by `session_bind._ensure_router_alive`; owns `RoutingIndex`, `RoutingPoller`, `IdleMonitor`, `InboundConsumerImpl`, single-instance flock gate, run-index, unrouted-audit
- `.claude/pipeline/comms/slack/__init__.py` — Slack adapter package marker
- `.claude/pipeline/comms/slack/provider.py` — `SlackProvider` + `build_slack_provider` factory; sole importer of `slack_bolt` / `slack_sdk` in the codebase (AC2)
- `.claude/pipeline/comms/slack/blocks.py` — `BUTTON_LETTERS`, `build_question_blocks`, `build_decision_blocks`, `encode_button_value`, `decode_button_payload`
- `.claude/pipeline/comms/slack/inbound.py` — `SlackInboundStream`; Bolt App + SocketModeHandler push-side adapter; cross-channel guard (B3); pipe-encoded action_id decoder (B6)
- `.claude/pipeline/comms/slack/recovery.py` — `recover_message_ts`; scans `conversations.replies` for crash-recovery round-trip

## How to add a new provider

### 1. Implement the CommsProvider protocol

Create `.claude/pipeline/comms/<name>/provider.py`. Your class must satisfy every method in `comms/provider.py::CommsProvider`. Key methods:

| Method | Purpose |
|--------|---------|
| `auth_preflight()` | Verify creds + scopes. Returns `AuthCheck`. |
| `post_simple(thread, kind, text)` | Post status notification to thread. |
| `post_question(thread, text, options, *, client_msg_id, ...)` | Post question with buttons. MUST embed `client_msg_id` in message metadata. |
| `post_decision(thread, text, options, *, client_msg_id)` | Post decision with buttons. |
| `recover_message_ts(thread, client_msg_id)` | Scan history for a prior post matching `client_msg_id`. Returns `MessageRef | None`. |
| `update_message(ref, new_body, *, lock)` | Edit/lock a message. |
| `post_confirmation(thread, ref, answer)` | Reply confirming a pick was recorded. |
| `post_ephemeral_error(thread, user_id, text)` | Ephemeral error visible only to `user_id`. |
| `open_thread(channel_hint, opening_text)` | Create a new thread. Returns `ThreadRef`. |
| `close_thread(thread, closing_text)` | Post closing reply. |
| `start_inbound(consumer, stop)` | Start push-side inbound transport. |
| `stop_inbound()` | Idempotent shutdown. |

Return types (`ThreadRef`, `MessageRef`, `QuestionPost`, `DecisionPost`, `AuthCheck`) are imported from `comms.types`. Use `types.MappingProxyType` for `provider_data` to enforce immutability.

### 2. Write a zero-arg factory

```python
def build_discord_provider() -> "DiscordProvider":
    from comms.env import load_env_file, default_env_path
    load_env_file(default_env_path())
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN required.")
    return DiscordProvider(bot_token=token)
```

### 3. Register in CommsRegistry

In `.claude/pipeline/comms/registry.py::_register_builtins`:

```python
def _register_builtins(reg: CommsRegistry) -> None:
    from .slack.provider import build_slack_provider
    reg.register("slack", build_slack_provider)

    from .discord.provider import build_discord_provider  # add this
    reg.register("discord", build_discord_provider)
```

### 4. Configure via pipeline.toml

Per project:
```toml
[comms]
provider = "discord"
```

Unknown provider name → `UnknownProviderError` listing registered names (AC8 / AC3).

### 5. What config keys your provider owns

Provider-specific config (tokens, channel ids, allowed users) lives in the env-file (`~/.claude/pipeline/slack.env.local` by default, override via `SLACK_ENV_FILE`). Use provider-namespaced env vars (e.g. `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`). The registry does NOT know about channels.

### 6. Inbound event stream

`start_inbound(consumer, stop)` must:
- Launch your own worker thread (daemon=True).
- Per event, normalize to `InboundEvent` with structured fields (`run_id`, `qd_id`, `option_index`) — no raw provider-encoded strings.
- Call `consumer.dispatch(event)` synchronously from your worker thread.
- Monitor `stop` (threading.Event); tear down transport when set.

Cross-provider concern: the cross-channel guard (B3) belongs inside YOUR adapter's inbound handler, not the router. The router trusts all events it receives are in-channel.

## On-disk layout

```
~/.claude/comms-router/           # host-level (not stowed)
├── router.pid                    # flock + PID (mode 0600)
├── router.log                    # daemon log (mode 0600)
├── unrouted/<ts>.json            # audit: events with no route or cross-channel
└── run-index/<run-id>.json       # per-run routing context

~/.claude/sessions/<sid>/
├── slack.json                    # session binding state (mode 0600)
│                                 # schema_version: 1; provider field v1-additive
└── inbox/<msg_ts>.json           # router-written inbound messages
```

`.comms-context.json` and `.comms-posting.lock` live per run-dir (`.pipeline/runs/<run-id>/`).

## Hard-cutover note (ADR-0004)

Legacy `~/.claude/slack-router/` and `.slack-context.json` artefacts are NOT read by the new code. One-shot reap of the legacy daemon happens in `session_bind._reap_legacy_slack_router` before the new daemon spawns. Pre-cutover in-flight state is forfeit. See `docs/adr/0004-comms-router-hard-cutover-no-legacy-fallback.md`.

## External dependencies

- `slack-bolt >= 1.18` — Slack adapter only (installed via `uv run --script` header)
- `filelock >= 3.13` — `pipeline_notify.py` `.comms-context.json` locking
