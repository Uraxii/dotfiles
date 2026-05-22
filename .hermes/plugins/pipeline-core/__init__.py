"""pipeline-core — Hermes plugin registering 8 deterministic pipeline tools.

Registration model (per `https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins`):
- `register(ctx)` is the entry point; Hermes calls it once at session start
  when `plugins.enabled` lists this plugin in ~/.hermes/config.yaml.
- Each tool registers with `ctx.register_tool(name, toolset, schema, handler)`.
- B1 fallback (Doctrine delta #3): if plugin-defined toolsets aren't grantable
  to subagents, switch every tool's `toolset` arg to "file" below, and
  subagents will get these tools transitively via their existing [file]
  grant. The pre-flight spike (sequencing step 0) determines which path.

Tool handlers live in `tools.py`. Schemas live in `schemas.py`.

Terminal-backend guard: pipeline-core requires `terminal.backend: local`
because worktree git ops run on the host. Non-local backends would break
visibility between terminal-tool writes (in container/remote) and host-side
git subprocess. Plugin refuses to load otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from . import schemas
from . import tools as tools_mod

# Toolset name. Flip to "file" if pre-flight spike shows plugin-defined
# toolset buckets aren't grantable via delegate_task(toolsets=[...]).
PIPELINE_TOOLSET = "pipeline"


class PluginGuardError(RuntimeError):
    """Raised when host config violates pipeline-core invariants."""


def _check_terminal_backend() -> None:
    """Block plugin load if terminal.backend != local.

    Hermes config lives at ~/.hermes/config.yaml. Read it directly; we
    can't rely on `ctx` exposing config at register time (docs are
    silent on this).
    """
    config_path = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "config.yaml"
    if not config_path.is_file():
        # No config to check — assume local default.
        return

    try:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return

    backend = (cfg.get("terminal") or {}).get("backend", "local")
    if backend != "local":
        raise PluginGuardError(
            f"pipeline-core requires terminal.backend: local "
            f"(got {backend!r}). Worktree git ops run on host; terminal "
            f"writes must be host-visible. See M6 / decision 9 in the port plan."
        )


# (tool_name, handler_callable, schema_dict) triples.
_TOOLS = [
    ("pipeline_artifact_slug", tools_mod.artifact_slug, schemas.ARTIFACT_SLUG),
    ("pipeline_verdict_parse", tools_mod.verdict_parse, schemas.VERDICT_PARSE),
    ("pipeline_dep_graph_compose", tools_mod.dep_graph_compose, schemas.DEP_GRAPH_COMPOSE),
    ("pipeline_revision_route", tools_mod.revision_route, schemas.REVISION_ROUTE),
    ("pipeline_worktree_lifecycle", tools_mod.worktree_lifecycle, schemas.WORKTREE_LIFECYCLE),
    ("pipeline_test_path_resolve", tools_mod.test_path_resolve, schemas.TEST_PATH_RESOLVE),
    ("pipeline_prod_diff_sha", tools_mod.prod_diff_sha, schemas.PROD_DIFF_SHA),
    ("pipeline_friction_audit", tools_mod.friction_audit, schemas.FRICTION_AUDIT),
]


def register(ctx) -> None:
    """Hermes plugin entry point. Called once at session start."""
    _check_terminal_backend()
    for name, handler, schema in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset=PIPELINE_TOOLSET,
            schema=schema,
            handler=handler,
        )
