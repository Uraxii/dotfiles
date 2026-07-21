# Spike: Advisor tool for full-resolution image critique

Date: 2026-07-20. Research only, no code. Labels: VERIFIED (confirmed in official docs), REASONED (derived from verified facts), ASSUMED (no source found, needs empirical test).

Sources:

- Advisor tool (API): https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool
- Vision (limits and token formula): https://platform.claude.com/docs/en/build-with-claude/vision
- Advisor in Claude Code: https://code.claude.com/docs/en/advisor
- Advisor blog: https://claude.com/blog/the-advisor-strategy
- Community field report (advisor blind spots): https://readysolutions.ai/blog/2026-05-23-claude-code-advisor-when-to-call-and-where-blind/

## Question 1: Do images reach the advisor?

- VERIFIED: The advisor "receives the executor's full transcript as quoted context in its input. That transcript includes your system prompt, the tool definitions, the prior turns and tool results, and the text the executor has produced so far in this turn." (API advisor doc, How it works.)
- VERIFIED: The executor cannot pass anything to the advisor directly. `server_tool_use.input` is always empty; "Nothing the executor puts in `input` reaches the advisor." The server constructs the advisor's view from the transcript. So the ONLY path for images is the executor conversation itself.
- VERIFIED (Claude Code doc): "The advisor always receives the full conversation, including every tool call and result."
- NOT VERIFIED for images specifically: no official doc enumerates `image` content blocks as part of the forwarded transcript. The phrase "quoted context" leaves open whether image blocks are rendered to the advisor as actual images or as placeholders. The community field report (159 logged calls) confirms transcript visibility but never tested images.
- REASONED: "full transcript including prior turns and tool results" most plausibly includes image blocks, since they are ordinary content blocks in those turns. But for a design whose whole point is vision critique, this must be empirically confirmed before committing.
- Suggested probe (cheap, definitive): send one distinctive image in the user turn, use `claude-opus-4-8` as advisor (plaintext `advisor_result`), and add the officially documented advisor-directed line in the user message, e.g. "(Advisor: describe the image in the conversation in one sentence.)". The API doc confirms the advisor sees user messages and follows advisor-addressed lines reliably. If the plaintext advice describes the image, images reach the advisor.

Verdict: transcript forwarding VERIFIED, image-block forwarding ASSUMED pending the probe above.

## Question 2: Image limits and billing on that path

All limits below from the official Vision doc (VERIFIED):

- Max dimensions per image: 8000x8000 px.
- Max size per image: 10 MB base64 on the Claude API (5 MB on Bedrock and Google Cloud).
- Images per request: 600 on the API for 1M-context models; 100 for 200k-context models; overall request size cap 32 MB usually binds first.
- Stricter rule: a request with more than 20 image or document blocks applies a lower per-image dimension limit (stay at or under 2000 px per side, or keep to 20 or fewer images).
- Resolution tiers: high-resolution (Fable 5, Mythos 5, Opus 4.8, Opus 4.7, Sonnet 5) allows 2576 px long edge and 4784 visual tokens per image. Standard tier (all others, including Sonnet 4.6 and Haiku 4.5) allows 1568 px long edge and 1568 visual tokens. Larger images are downscaled server-side, aspect ratio preserved.
- Token formula: tokens = ceil(width/28) x ceil(height/28), after any downscale.

Billing for the advisor call (VERIFIED, API advisor doc, Usage and billing):

- The advisor runs as a separate sub-inference billed at the ADVISOR model's rates. It appears in `usage.iterations[]` as `type: "advisor_message"` with its own input/output token counts. Executor iterations bill at the executor model's rates.
- REASONED: if images are in the transcript, each advisor call re-pays the image's vision tokens as advisor-model input tokens (the advisor re-reads the full transcript each call). Advisor-side caching is off by default; enable the tool-level `caching` option when expecting 3 or more advisor calls per conversation (VERIFIED break-even guidance).
- VERIFIED: top-level `max_tokens` and task budgets do not bound the advisor; cap advisor output with `max_tokens` on the tool definition (min 1024; 2048 recommended).

Design implication (REASONED): both executor and Fable-5 advisor are high-resolution tier, so a full-res critique path tops out at 2576 px long edge / 4784 tokens per image regardless of source resolution. "Full resolution" above ~1914x1914 (square) buys nothing; the server downscales it anyway.

## Question 3: Advisor from inside a spawned subagent

Previously ASSUMED, now VERIFIED at both layers:

- Claude Code layer (official, code.claude.com advisor doc): "Subagents inherit the configured advisor and apply the same pairing check against their own model." And: "Subagents whose own model satisfies the pairing may still use the advisor" even when the main model's pairing fails. So Agent-tool children can consult the advisor.
- API layer (REASONED from official docs): the advisor is an ordinary server tool on `/v1/messages`; nothing restricts it by caller, and it is even supported in the Batches API (VERIFIED). A subagent making its own Messages API call with the beta header works like any other client.

Two blocking caveats for THIS design (both VERIFIED):

1. Claude Code currently does NOT offer Fable 5 as the advisor. The `/advisor` picker shows "Fable 5 (temporarily unavailable)" (dimmed), and `/advisor fable` and `--advisor fable` are rejected. A remote rollout gate controls its return. A Fable-5 advisor works today only via direct API calls (`advisor_20260301` with `model: "claude-fable-5"`), not through Claude Code's built-in advisor.
2. A Fable 5 (or Mythos 5) advisor returns `advisor_redacted_result` with `encrypted_content`: the executor reads the advice server-side but the client never sees the text. An Opus 4.8 advisor returns plaintext `advisor_result`. If the workflow needs to log or display the advisor's aesthetic verdict, use Opus 4.8 as advisor or accept opacity. Community note: a TTL bug on encrypted advisor results reportedly broke Claude Code session recovery (GitHub issue #49994, unverified).

Also VERIFIED: the API advisor doc lists availability as Claude API and Claude Platform on AWS (beta); the Claude Code doc lists it as Anthropic API only in that surface. Not on Bedrock, Vertex, or Foundry.

## Question 4: Vision token math for ComfyUI outputs

Formula (VERIFIED): tokens = ceil(w/28) x ceil(h/28); high-res tier caps at 2576 px long edge and 4784 tokens; standard tier at 1568 px and 1568 tokens. Costs use Fable 5 / Mythos 5 at $10 per MTok input, Opus 4.8 at $5, Sonnet 4.6 at $3 (skill-cached pricing table dated 2026-06-24 plus the Vision doc's Opus 4.8 example; confirm at https://claude.com/pricing before budgeting).

1024x1024 PNG:

- Not downscaled on either tier. ceil(1024/28) = 37; 37 x 37 = 1369 tokens (REASONED from the verified formula; the doc's own 1000x1000 example is 1296 tokens, consistent).
- Per image input cost: Fable 5 advisor ~$0.0137; Opus 4.8 ~$0.0068; Sonnet 4.6 executor ~$0.0041.

2048x2048 PNG:

- High-res tier: long edge 2048 fits under 2576, but 74 x 74 = 5476 tokens exceeds the 4784 cap, so it is downscaled to about 1914x1914, giving 69 x 69 = 4761 tokens (REASONED from the verified rule; matches the doc's 3840x2160 -> 4784 example).
- Standard tier (e.g. Sonnet 4.6 executor): downscaled to about 1092x1092 = 1521 tokens (VERIFIED, doc table row).
- Per image input cost at ~4761 tokens: Fable 5 ~$0.048; Opus 4.8 ~$0.024.

Per advisor call, the image tokens are paid again at advisor rates on top of the text transcript, and again on every subsequent advisor call unless tool-level `caching` is enabled.

## Bottom line for the art-workflow design

- The mechanism (executor sees full-res image, consults stronger advisor mid-generation) is plausible and cheap per image, but image-to-advisor forwarding is the single unverified load-bearing assumption. Run the one-request probe before building.
- Use Opus 4.8 as the advisor if the critique text must be visible to the orchestrator; Fable 5 advice is encrypted client-side and Fable is currently blocked as an advisor inside Claude Code anyway.
- Send critique images at or under 2576 px long edge (square: ~1914 px); anything larger is silently downscaled.
