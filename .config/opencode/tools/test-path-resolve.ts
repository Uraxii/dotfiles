import path from "node:path"
import { z } from "zod"

export default {
  description:
    "Resolve canonical test path glob set for a pipeline run. " +
    "Returns newline-separated globs. Reads test-paths.txt if present, else returns defaults.",
  args: {
    run_dir: z.string().describe("Pipeline run directory path"),
  },
  async execute(
    args: { run_dir: string },
    _context: { worktree: string }
  ) {
    const home = process.env.HOME
    if (!home) throw new Error("HOME is not set")
    const script = path.join(
      home,
      ".config/opencode/tools/test-path-resolve.py"
    )
    try {
      const result =
        await Bun.$`python3 ${script} --run-dir ${args.run_dir}`.text()
      return result.trim()
    } catch (err) {
      throw new Error(
        `test-path-resolve failed: ${err instanceof Error ? err.message : String(err)}`
      )
    }
  },
}
