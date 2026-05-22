"""pipeline-core tool schemas (LLM-visible JSON Schema definitions).

Each schema follows Hermes/JSON-Schema convention:
    {
      "name": "<tool_name>",
      "description": "<one-line purpose>",
      "parameters": {
        "type": "object",
        "properties": {...},
        "required": [...]
      }
    }

Tool handler in tools.py receives (args: dict, **kwargs) and MUST return a
JSON string (json.dumps). Errors return {"error": "msg"} string, NEVER raise.
"""

from __future__ import annotations

ARTIFACT_SLUG = {
    "name": "pipeline_artifact_slug",
    "description": "Generate a canonical pipeline artifact-id slug of shape adj-mid-noun-hex6 (e.g. crisp-cooking-plum-5d362a). Used as run-id, plan-id, and branch prefix.",
    "parameters": {
        "type": "object",
        "properties": {
            "seed": {
                "type": "string",
                "description": "Optional seed for deterministic slug. Empty/'none' = random.",
                "default": "none",
            }
        },
        "required": [],
    },
}

VERDICT_PARSE = {
    "name": "pipeline_verdict_parse",
    "description": "Glob verdict-<type>-r<N>.md files in a run dir, pick the max-N file for the given verdict type, parse YAML frontmatter, return the parsed verdict + revision number.",
    "parameters": {
        "type": "object",
        "properties": {
            "run_dir": {"type": "string", "description": "Absolute path to <repo>/.pipeline/runs/<artifact-id>/"},
            "type": {"type": "string", "description": "Verdict type: design | code | ops | security | test | review-standards | review-spec | friction"},
        },
        "required": ["run_dir", "type"],
    },
}

DEP_GRAPH_COMPOSE = {
    "name": "pipeline_dep_graph_compose",
    "description": "Compose ordered role execution graph from brief + plan. Topological sort over role deps; injects decision-elicitation stages after declared after: roles. Returns {ordered_roles, decision_inject_points, K, warnings}.",
    "parameters": {
        "type": "object",
        "properties": {
            "payload_json": {
                "type": "string",
                "description": "JSON string w/ {brief_path, plan_path?, decision_points?, roles_included, shards?}",
            }
        },
        "required": ["payload_json"],
    },
}

REVISION_ROUTE = {
    "name": "pipeline_revision_route",
    "description": "Map a verdict file to next pipeline action. Returns {action: approved|revise|halt, target_role, revision_n, reason, loop_cap_hit, verdict_summary}.",
    "parameters": {
        "type": "object",
        "properties": {
            "verdict_path": {"type": "string", "description": "Absolute path to verdict-<type>-r<N>.md"}
        },
        "required": ["verdict_path"],
    },
}

WORKTREE_LIFECYCLE = {
    "name": "pipeline_worktree_lifecycle",
    "description": "Git worktree primitives for sharded builds. ops: create (new worktree+branch), probe (status), cleanup (remove), scope-check (verify edits in scope globs), drift-intersect (detect base_sha drift touching shard scope or doctrine paths).",
    "parameters": {
        "type": "object",
        "properties": {
            "op": {
                "type": "string",
                "enum": ["create", "probe", "cleanup", "scope-check", "drift-intersect"],
            },
            "run_dir": {"type": "string", "description": "Run dir (for sidecar / metadata)"},
            "worktree_path": {"type": "string", "description": "Absolute worktree path"},
            "branch": {"type": "string", "description": "Branch name (e.g. pipeline/<artifact-id>/s1)"},
            "base_ref": {"type": "string", "description": "Base branch (e.g. main)"},
            "base_sha": {"type": "string", "description": "SHA at run start (drift detection)"},
            "scope": {"type": "array", "items": {"type": "string"}, "description": "Path globs for scope-check / drift-intersect"},
        },
        "required": ["op"],
    },
}

TEST_PATH_RESOLVE = {
    "name": "pipeline_test_path_resolve",
    "description": "Resolve canonical test path globs for a run. Reads optional <run_dir>/test-paths.txt manifest (one glob per line) + ecosystem defaults. Returns expanded path list.",
    "parameters": {
        "type": "object",
        "properties": {
            "run_dir": {"type": "string"},
            "repo_root": {"type": "string", "description": "Repo root for glob expansion"},
        },
        "required": ["run_dir"],
    },
}

PROD_DIFF_SHA = {
    "name": "pipeline_prod_diff_sha",
    "description": "Compute SHA1 of production-code diff vs base_sha, excluding test paths. Used for test-only revision pin validation (prod_diff_sha unchanged => prior code verdict still pinned).",
    "parameters": {
        "type": "object",
        "properties": {
            "run_dir": {"type": "string"},
            "base_sha": {"type": "string"},
            "repo_root": {"type": "string"},
            "exclude_globs": {"type": "array", "items": {"type": "string"}, "description": "Globs to exclude (defaults to common test paths)"},
        },
        "required": ["base_sha", "repo_root"],
    },
}

FRICTION_AUDIT = {
    "name": "pipeline_friction_audit",
    "description": "Deterministic post-run audit of pipeline doctrine adherence. Non-gating, meta-only. Writes friction-findings-r<N>.md to run dir. Returns {findings_count, severity_breakdown, output_path}.",
    "parameters": {
        "type": "object",
        "properties": {
            "run_dir": {"type": "string"},
        },
        "required": ["run_dir"],
    },
}
