import { createSdkMcpServer, tool } from "@anthropic-ai/claude-agent-sdk"
import { z } from "zod"
import path from "node:path"
import { promisify } from "node:util"
import { execFile as execFileCb } from "node:child_process"

const execFile = promisify(execFileCb)

const artifactSlug = tool(
  "artifact_slug",
  [
    "Generate canonical pipeline artifact IDs for plans and runs.",
    "Use when minting a new plan ID or pipeline run ID.",
    "Returns a human-readable identifier in the format <slug>-<hex6>.",
    "Do not use for arbitrary naming unrelated to pipeline artifacts.",
  ].join(" "),
  {
    seed: z.number().optional().describe("Optional deterministic seed for testing only"),
  },
  async (args, _extra) => {
    const script = path.join(process.cwd(), ".config/opencode/tools/artifact-slug.py")
    const cmdArgs = args.seed === undefined ? [script] : [script, "--seed", String(args.seed)]
    const { stdout } = await execFile("python3", cmdArgs)
    const artifactId = stdout.trim()
    const match = /^(.*)-([a-f0-9]{6})$/.exec(artifactId)

    return {
      content: [{ type: "text", text: artifactId }],
      structuredContent: {
        artifact_id: artifactId,
        slug: match?.[1] ?? artifactId,
        hex: match?.[2] ?? null,
      },
    }
  },
  {
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false,
    },
  },
)

export function createArtifactSlugServer() {
  return createSdkMcpServer({
    name: "pipeline",
    version: "1.0.0",
    tools: [artifactSlug],
  })
}
