# Agent Creation — Session Instructions

## Role System

This project uses a multi-agent role system. On every session startup:

1. Read `core-memory.md` for cross-cutting guidelines
2. Read the current project's `agent-memory.md` (if it exists) for domain knowledge
3. Check `taskboard.md` for in-progress or assigned work

When doing substantial work (new features, multi-step changes), use the role pipeline defined in `agents/*/role.md`. Prefix responses with `**[RoleName]**` when adopting a role.

### Pipeline modes

- **Full pipeline** (new features, ambiguous scope): Planner → Architect → Security Auditor (threat model) → [GRC Analyst (compliance review)] → Skeptic → Developer → Security Auditor (code review) → [GRC Analyst (implementation review)] → Reviewer → Tester
- **Lightweight pipeline** (bug fixes, clear-scope changes): Developer → Skeptic post-implementation review → Security Auditor (code review) → Tester runs suite
- The **Skeptic review**, **Security Auditor review**, and **friction report** are mandatory in both modes — they are never skipped
- **GRC Analyst** is optional — invoked by the Planner only when the project has a compliance surface (personal data, regulated data, named regulatory framework, or formal risk management mandate). See `agents/grc/role.md` for invocation criteria.

### After implementation

- Run the test suite and fix stale tests
- Do a runtime verification (browser or equivalent)
- Write a friction report with a **Memory updates** section:
  - Universal lessons → `agents/<role>/memory.md`
  - Project domain knowledge → `<project>/agent-memory.md`

## Project Structure

- `agents/` — Role definitions, per-role memory files
- `core-memory.md` — Shared guidelines all roles follow
- `templates/` — Templates for creating new roles
- `practice-projects/` — Game projects built with this system
