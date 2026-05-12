import path from "node:path"
import { z } from "zod"

const SCOPES = ["run", "background"] as const

export default {
  description:
    "Generate memory curation diff artifact. READ-ONLY — never mutates memory files. " +
    "Returns path to written diff file under ~/.pipeline/dreams/",
  args: {
    scope: z.enum(SCOPES).describe("run: current run only; background: all memory"),
    run_id: z.string().optional().describe("Pipeline run artifact ID (for scope=run)"),
  },
  async execute(
    args: { scope: (typeof SCOPES)[number]; run_id?: string },
    _context: { worktree: string }
  ) {
    const home = process.env.HOME
    if (!home) throw new Error("HOME is not set")
    const script = path.join(home, ".config/opencode/tools/dream-generate.py")
    const cmd = ["python3", script, "--scope", args.scope]
    if (args.run_id) cmd.push("--run-id", args.run_id)
    try {
      const result = await Bun.$`${cmd}`.text()
      return result.trim()
    } catch (err) {
      throw new Error(
        `dream-generate failed: ${err instanceof Error ? err.message : String(err)}`
      )
    }
  },
}
