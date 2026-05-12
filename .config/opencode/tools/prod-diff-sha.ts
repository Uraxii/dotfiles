import path from "node:path"
import { z } from "zod"

export default {
  description:
    "Compute SHA1 of production-code diff vs base_sha, excluding test paths. " +
    "Returns 40-char hex SHA or 40 zeros for empty diff.",
  args: {
    base_sha: z.string().describe("Base git SHA to diff from"),
    head: z.string().default("HEAD").describe("Head ref or SHA"),
    test_paths_file: z
      .string()
      .optional()
      .describe("Optional path to test-paths.txt glob list"),
  },
  async execute(
    args: { base_sha: string; head: string; test_paths_file?: string },
    _context: { worktree: string }
  ) {
    const home = process.env.HOME
    if (!home) throw new Error("HOME is not set")
    const script = path.join(home, ".config/opencode/tools/prod-diff-sha.py")
    const cmd = ["python3", script, "--base-sha", args.base_sha, "--head", args.head]
    if (args.test_paths_file) {
      cmd.push("--test-paths-file", args.test_paths_file)
    }
    try {
      const result = await Bun.$`${cmd}`.text()
      return result.trim()
    } catch (err) {
      throw new Error(
        `prod-diff-sha failed: ${err instanceof Error ? err.message : String(err)}`
      )
    }
  },
}
