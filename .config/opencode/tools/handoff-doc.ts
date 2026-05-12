import path from "node:path"
import { z } from "zod"

export default {
  description:
    "Write a handoff document for agent session rotation. " +
    "Returns the path to the written handoff file.",
  args: {
    role: z.string().describe("Agent role name (e.g. build, architect)"),
    run_dir: z.string().describe("Pipeline run directory path"),
    next_focus: z.string().describe("What the next session should focus on"),
  },
  async execute(
    args: { role: string; run_dir: string; next_focus: string },
    _context: { worktree: string }
  ) {
    const home = process.env.HOME
    if (!home) throw new Error("HOME is not set")
    const script = path.join(home, ".config/opencode/tools/handoff-doc.py")
    try {
      const result =
        await Bun.$`python3 ${script} --role ${args.role} --run-dir ${args.run_dir} --next-focus ${args.next_focus}`
          .text()
      return result.trim()
    } catch (err) {
      throw new Error(
        `handoff-doc failed: ${err instanceof Error ? err.message : String(err)}`
      )
    }
  },
}
