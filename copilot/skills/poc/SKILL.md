---
name: poc
description: Spin up the multi-agent dev team to handle a task end-to-end. Hands the whole request to the tech-lead orchestrator, which triages it, breaks it into phases, and delegates to specialists (requirements-clarifier, architect-designer, implementation-specialist, test-automation-engineer, skeptic-gate). Use when the user types "POC", says "use the team", "spin up the tech-lead", "orchestrate this", or wants a non-trivial task handled by the full fleet instead of solo.
---

# POC — spin up the dev team

This skill is a thin launcher. It does **not** do the work itself. It hands the
user's request to the `tech-lead` agent, which owns triage, phasing, and
delegation to the specialist fleet.

## What to do when this skill fires

1. **Capture the task.** Take everything the user asked for (the prompt that
   triggered this skill, minus the `poc` / "use the team" trigger words) plus any
   relevant context already in the conversation — files under discussion, the
   working directory, constraints, prior decisions.

2. **Delegate to tech-lead.** Call the `agent` tool with agent `tech-lead`. Pass a
   single, self-contained briefing — the sub-agent does not see this conversation:
   - The full task, verbatim where wording matters.
   - Relevant context (repo/cwd, target files, constraints, acceptance criteria).
   - The instruction: *"Orchestrate this per your operating protocol. Triage,
     phase the work, and delegate to specialists. Run the skeptic-gate challenge
     check before any risky change ships. Return an integrated result plus any
     clarifying questions or non-PASS gate verdicts."*

3. **Stay out of the way.** Do not pre-solve, pre-architect, or pre-implement.
   tech-lead decides what is trivial (handles directly) vs. what needs specialists.

4. **Relay the outcome.** Surface tech-lead's integrated result to the user. If it
   returns clarifying questions (requirements-clarifier) or a non-PASS verdict
   (skeptic-gate: BLOCK / NEEDS_TEST / NEEDS_ARCH_REVIEW / NEEDS_REQUIREMENTS),
   present those first and stop for the user — do not paper over a gate failure.

## Notes

- The whole fleet runs on the available model catalog (currently `claude-haiku-4.5`
  / `gpt-5-mini`); tech-lead and its specialists inherit the session model.
- Delegation nests: this skill → tech-lead → specialist. That depth is supported.
- For a single trivial edit, you do not need POC — tech-lead would just do it
  inline anyway, but invoking solo is faster.
