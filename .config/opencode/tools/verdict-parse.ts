import path from "node:path"
import { z } from "zod"

const VERDICT_TYPES = [
  "design",
  "code",
  "ops",
  "review",
  "test-audit",
  "friction",
] as const

export default {
  description:
    "Parse latest pipeline verdict file of given type from run directory. " +
    "Returns JSON with verdict, role, review_type, loops, revision, prod_diff_sha, path.",
  args: {
    run_dir: z.string().describe("Pipeline run directory path"),
    type: z
      .enum(VERDICT_TYPES)
      .describe("Verdict type: design|code|ops|review|test-audit|friction"),
  },
  async execute(
    args: { run_dir: string; type: (typeof VERDICT_TYPES)[number] },
    _context: { worktree: string }
  ) {
    const home = process.env.HOME
    if (!home) throw new Error("HOME is not set")
    const script = path.join(
      home,
      ".config/opencode/tools/verdict-parse.py"
    )
    try {
      const result =
        await Bun.$`python3 ${script} --run-dir ${args.run_dir} --type ${args.type}`
          .text()
      return result.trim()
    } catch (err) {
      throw new Error(
        `verdict-parse failed: ${err instanceof Error ? err.message : String(err)}`
      )
    }
  },
}
