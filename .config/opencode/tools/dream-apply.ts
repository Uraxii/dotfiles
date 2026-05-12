import path from "node:path"
import { z } from "zod"

export default {
  description:
    "USER-ONLY: Apply dream diff to memory files. " +
    "Returns path to written apply-receipt. " +
    "NEVER invoke from pipeline agents — invoke via /dream-apply slash command only.",
  args: {
    diff_path: z
      .string()
      .describe("Path to dream diff file (e.g. ~/.pipeline/dreams/TIMESTAMP-scope.diff.md)"),
  },
  async execute(
    args: { diff_path: string },
    _context: { worktree: string }
  ) {
    const home = process.env.HOME
    if (!home) throw new Error("HOME is not set")
    const script = path.join(home, ".config/opencode/tools/dream-apply.py")
    try {
      const result =
        await Bun.$`python3 ${script} --diff-path ${args.diff_path}`.text()
      return result.trim()
    } catch (err) {
      throw new Error(
        `dream-apply failed: ${err instanceof Error ? err.message : String(err)}`
      )
    }
  },
}
