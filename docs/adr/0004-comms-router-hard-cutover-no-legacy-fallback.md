# ADR-0004: comms-router hard cutover — no legacy read-fallback

**Date**: 2026-05-15
**Status**: Accepted
**Context**: comms-provider-abstraction refactor (run `mighty-drifting-rivest-f581c0`)

## Context

The comms-provider abstraction refactor renames on-disk artefacts:
- `~/.claude/slack-router/` → `~/.claude/comms-router/`
- `.slack-context.json` → `.comms-context.json`
- `.slack-posting.lock` → `.comms-posting.lock`

A migration shim (read both names, prefer new) was considered and rejected.

## Decision

**Hard cutover. No legacy read-fallback.**

New code reads ONLY `.comms-context.json` and ONLY spawns `~/.claude/comms-router/`. One-shot legacy-PID reap in `session_bind._reap_legacy_slack_router` SIGTERMs the old `slack_router.py` daemon (same-uid only; cross-uid logs warning + skips per B5) before the new daemon spawns. Pre-cutover in-flight question/decision state is forfeit.

### Reap algorithm

1. If `~/.claude/slack-router/router.pid` absent: no-op (already migrated or fresh install).
2. Read legacy pid. Unreadable: log warning + skip kill + rmtree.
3. Stat `/proc/<pid>` owner uid.
   - Cross-uid: log warning + skip reap + continue (mirrors legacy `_reap_legacy_listeners` tolerance). New daemon spawns alongside; Socket Mode load-balances events between them.
   - Process already gone: unlink pidfile + rmtree.
4. Same uid: identity check via `_verify_pid_is_slack_router(pid)` (checks `/proc/<pid>/cmdline`).
   - Not a slack_router process (stale pid): log warning + skip kill.
5. SIGTERM → poll 2s → SIGKILL → unlink → rmtree.
6. Hard-error only when same-uid kill raises unexpected EPERM.

## Consequences

**Positive:**
- Zero ongoing read-fallback complexity.
- Single code path for artefact reads.
- AC2 audit trivial: `grep slack_bolt .claude/pipeline/ | grep -v comms/slack/` must return empty.

**Negative:**
- Mid-flight runs at cutover lose idempotency tokens (`.slack-posting.lock` / `.slack-context.json` state is not migrated).
- User-visible risk: if a question/decision was posted but the context file not yet updated at cutover, manual retry may double-post. Probability low; impact minimal for single-user dotfiles.

## Rollback

The decision is **irreversible for in-flight runs at the cutover moment** — their `.slack-context.json` state is not migrated.

**Code-level rollback is mechanical but not zero-cost**: requires manual rename of the new artefact paths back to legacy (`~/.claude/comms-router/` → `~/.claude/slack-router/`, `.comms-context.json` → `.slack-context.json` per run-dir), redeploy of the old `slack_router.py`, and re-spawn of the legacy daemon. Any runs created post-cutover under the new paths must be drained or manually fixed up before rollback. There is no automated downgrade tool.

## Alternatives rejected

**(a) Read-fallback shim** — leaves the legacy filename in code indefinitely, contradicts the "rename" semantic, adds ongoing maintenance surface.

**(b) Version-flagged migration tool** — over-engineered for a single-user dotfiles repo; the cutover window is a deliberate deploy event.
