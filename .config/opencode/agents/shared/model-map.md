# Model Map

Agents specify `tier` in frontmatter. Resolve to vendor model below.

## Tiers

| Tier | Purpose |
|------|---------|
| high | Critical review, gating, complex reasoning |
| mid | Implementation, design, research |
| low | Summarization, memory maintenance, friction |

## Vendor Models

| Tier | anthropic | openai | google |
|------|-----------|--------|--------|
| high | claude-opus-4-6 | o3 | gemini-2.5-pro |
| mid | claude-sonnet-4-6 | gpt-4.1 | gemini-2.5-flash |
| low | claude-haiku-4-5-20251001 | gpt-4.1-mini | gemini-2.0-flash |

## Agent Tiers

| Agent | Tier |
|-------|------|
| planner | high |
| progenitor | high |
| reviewer | high |
| security-auditor | high |
| skeptic | high |
| architect | mid |
| developer | mid |
| orchestrator | mid |
| researcher | mid |
| tester | mid |
| ux-designer | mid |
| friction-reviewer | low |
| monitor | low |

## Resolution
Orchestrator reads active vendor → resolves tier → spawns agent w/ correct model.
