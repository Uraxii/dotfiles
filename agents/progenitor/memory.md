# Progenitor — Memory

## Agents Created

| Date | Agent | Purpose | Status |
|------|-------|---------|--------|
| 2026-03-11 | architect | Design system architecture, define patterns, make technology decisions | Active |
| 2026-03-11 | developer | Write production code implementing designs from the Architect | Active |
| 2026-03-11 | reviewer | Review code and designs for quality, consistency, and correctness | Active |
| 2026-03-11 | tester | Design test strategies, write test cases, find bugs adversarially | Active |
| 2026-03-11 | planner | Manage scope, tasks, dependencies, priorities, and project progress | Active |
| 2026-03-11 | documenter | Create and maintain living documentation for the project | Active |
| 2026-03-11 | devops | Manage CI/CD, deployment, infrastructure, and operational reliability | Active |
| 2026-03-11 | security-auditor | Review for vulnerabilities, threat model, enforce security policies | Active |
| 2026-03-11 | skeptic | Critical gatekeeper — must approve designs and plans before Developer receives work | Active |
| 2026-03-12 | monitor | Reviews agent memories, distills cross-cutting knowledge into core-memory.md | Active |

## Decisions & Notes

### 2026-03-11 — Initial agent creation
Created the full core team for scalable software projects. Rationale: Architect and Planner form the foundation (design + coordination), Developer and Reviewer form the build loop, Tester provides adversarial quality assurance, Documenter prevents knowledge decay, DevOps bridges dev-to-production, and Security Auditor ensures dedicated security perspective. All agents use markdown files for roles, memory, and inboxes.

### 2026-03-11 — Skeptic role created
Added the Skeptic as a critical gatekeeper in the workflow. The Skeptic reviews both Architect designs and Planner plans and must be convinced they are sound before any work is passed to the Developer. Updated Architect, Planner, and Developer roles to enforce this gate. This prevents half-baked designs from reaching implementation.

### 2026-03-12 — Monitor role created
Added the Monitor to review all agent memory files and distill cross-cutting knowledge into a shared `core-memory.md` file. Added a `## Startup` section to every agent's role requiring them to read `core-memory.md` on activation. Updated `templates/role-template.md` to include the Startup section for future agents. This ensures critical lessons and guidelines propagate system-wide.

### 2026-03-12 — System-wide infrastructure improvements
Based on friction report from practice projects, implemented 5 changes:
1. Created unified `messages.md` — replaces per-agent inboxes for same-session communication
2. Created `taskboard.md` — explicit task tracking with status, owner, and blockers
3. Added single-agent mode to `core-memory.md` — reduces file I/O ceremony when one agent plays all roles
4. Updated Planner/Architect/Skeptic for joint plan+design submissions to avoid circular dependencies
5. Monitor seeded `core-memory.md` with 6 bootstrapping guidelines from first project run
All 11 agent roles updated to reference messages.md, taskboard.md, and include taskboard in startup.

### 2026-03-12 — Researcher role created
Added the Researcher to fill the pre-planning domain research gap identified in the Glamour Guesser friction report. The Planner and Architect both needed domain knowledge (Eorzea Collection's API availability, Cloudflare constraints) before they could scope or design, but no existing role owned that investigation. The Researcher investigates external systems, APIs, domain concepts, and feasibility before planning begins. Delivers structured research briefs. Updated Planner, Architect, and Skeptic roles with Researcher relationships. Updated Planner instructions to include a research-first step.

### 2026-03-16 — Security Auditor formally integrated into pipeline
Updated `CLAUDE.md` pipeline modes and `security-auditor/role.md` to formally wire the Security Auditor into both pipeline modes. Previously the role existed but was not referenced in any pipeline stage. Changes:
- Full pipeline: Security Auditor now runs twice — after Architect (threat model before Skeptic gate) and after Developer (code review before Reviewer)
- Lightweight pipeline: Security Auditor runs after Skeptic (code review before Tester)
- Added explicit boundary with Reviewer: Security Auditor owns vulnerability classes, Reviewer owns code quality
- Added Pipeline Position table to role.md and split Instructions into design-time and code-time sections
- Updated Skeptic relationship to reflect that the Skeptic uses the threat model report as input to its design gate

### 2026-03-12 — Data Curator role created
Added the Data Curator to own the sourcing, validation, and maintenance of domain-specific datasets. The Glamour Guesser required 36 curated glamour entries with accurate FFXIV gear names — an activity that fell between roles (Developer wrote the data, but accuracy verification needed domain expertise outside code review or testing). The Data Curator ensures embedded data is accurate, complete, and properly structured. Updated Architect and Developer roles with Data Curator relationships.
