import path from "node:path"

export default {
  description: "Generate one canonical pipeline artifact ID in format <slug>-<hex6>. Call once when minting a new plan or run ID, then bind and reuse the exact returned value for all paths in that artifact lifecycle.",
  args: {},
  async execute(_args: Record<string, never>, context: { worktree: string }) {
    const home = process.env.HOME
    if (!home) {
      throw new Error("HOME is not set")
    }

    const script = path.join(home, ".config/opencode/tools/artifact-slug.py")

    const artifactId = (await Bun.$`python3 ${script}`.text()).trim()
    return `artifact_id=${artifactId}`
  },
}
