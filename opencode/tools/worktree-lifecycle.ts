import path from "node:path"
import { z } from "zod"

const OPS = ["create", "probe", "cleanup", "scope-check"] as const

export default {
  description:
    "Pipeline shard worktree lifecycle: create, probe (stale check), cleanup, scope-check. " +
    "Returns JSON with status and relevant fields.",
  args: {
    op: z.enum(OPS).describe("Operation: create|probe|cleanup|scope-check"),
    run_id: z.string().optional().describe("Pipeline run artifact ID"),
    shard_id: z.string().optional().describe("Shard ID e.g. s1"),
    base_sha: z.string().optional().describe("Base git SHA"),
    repo_root: z.string().optional().describe("Absolute path to repo root"),
    worktree_path: z.string().optional().describe("Worktree path for probe/cleanup"),
    head: z.string().optional().default("HEAD").describe("Head ref for scope-check"),
    scope_globs: z
      .array(z.string())
      .optional()
      .describe("Scope globs for scope-check"),
  },
  async execute(
    args: {
      op: (typeof OPS)[number]
      run_id?: string
      shard_id?: string
      base_sha?: string
      repo_root?: string
      worktree_path?: string
      head?: string
      scope_globs?: string[]
    },
    _context: { worktree: string }
  ) {
    const home = process.env.HOME
    if (!home) throw new Error("HOME is not set")
    const script = path.join(home, ".config/opencode/tools/worktree-lifecycle.py")
    const cmd = ["python3", script, "--op", args.op]
    if (args.run_id) cmd.push("--run-id", args.run_id)
    if (args.shard_id) cmd.push("--shard-id", args.shard_id)
    if (args.base_sha) cmd.push("--base-sha", args.base_sha)
    if (args.repo_root) cmd.push("--repo-root", args.repo_root)
    if (args.worktree_path) cmd.push("--worktree-path", args.worktree_path)
    if (args.head) cmd.push("--head", args.head)
    if (args.scope_globs?.length) cmd.push("--scope-globs", ...args.scope_globs)
    try {
      const result = await Bun.$`${cmd}`.text()
      return result.trim()
    } catch (err) {
      throw new Error(
        `worktree-lifecycle failed: ${err instanceof Error ? err.message : String(err)}`
      )
    }
  },
}
