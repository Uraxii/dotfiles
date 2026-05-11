import { query } from "@anthropic-ai/claude-agent-sdk"
import { createArtifactSlugServer } from "./artifact-slug-server"

const pipelineServer = createArtifactSlugServer()

for await (const message of query({
  prompt: "Mint one new canonical pipeline artifact ID.",
  options: {
    mcpServers: { pipeline: pipelineServer },
    allowedTools: ["mcp__pipeline__artifact_slug"],
  },
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result)
  }
}
