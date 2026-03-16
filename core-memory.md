# Core Memory

**All agents must read this file on startup.** It contains system-wide guidelines, lessons, and facts distilled from individual agent memories by the Monitor.

---

## Operating Modes

### Single-Agent Mode
When one agent is playing all roles in the same session:
- **Skip inbox and message log I/O** — announce role switches inline instead
- **Adopt each role's mindset and constraints** — the thinking is what matters, not the ceremony
- **Write to memory only at milestones** — not every micro-decision
- **Update `taskboard.md` at the start and end** of a work session, not per-step
- The Skeptic still critiques adversarially. Roles still enforce boundaries. Only the file I/O is reduced.
- Infrastructure and tooling work benefits disproportionately from the full role pipeline — the Skeptic catches issues that would cause cascading test failures. Feature implementation has a lower payoff ratio but still benefits from the design gate.

### Multi-Agent Mode (default)
When work spans multiple sessions or multiple agents:
- Use `messages.md` for all inter-agent communication with status tags
- Use `taskboard.md` to track handoffs and assignments
- Use individual `inbox.md` files only for async cross-session messages
- Follow full role protocols including memory updates

---

## Guidelines

### Role boundary: Planners must not make architectural decisions
- **Source:** Skeptic — 2026-03-12
- **Guideline:** The Planner scopes and sequences work. Technology choices, file structure, and design patterns are the Architect's responsibility. If a plan contains phrases like "use X framework" or "single-file approach," it has overstepped.

### Joint submissions reduce circular dependencies
- **Source:** Friction report — 2026-03-12
- **Guideline:** When architecture and planning are deeply intertwined, the Planner and Architect should collaborate first, then submit a joint plan+design package to the Skeptic. This avoids the chicken-and-egg problem of plans needing designs and designs needing scope.

### The state/update/render pattern scales well for browser apps
- **Source:** Architect — 2026-03-12
- **Guideline:** For browser-based projects, use unidirectional data flow: a state object, a pure update function, and a render function. This pattern scaled from trivial (Rock Paper Scissors) through complex (Chess) without modification.

### The Skeptic genuinely improves quality — do not skip it
- **Source:** Friction report — 2026-03-12
- **Guideline:** The Skeptic gate caught real design gaps (castling detail, scoping omissions) and role boundary violations. Even when it feels like overhead, it prevents issues from reaching implementation. Do not bypass.

### Use `messages.md` over individual inboxes for same-session work
- **Source:** Friction report — 2026-03-12
- **Guideline:** A single unified message log with status tags (`[PENDING]`, `[DONE]`) is far more efficient than maintaining 11 separate inbox files. Reserve individual `inbox.md` for async cross-session use only.

### Soft roles need explicit task tracking to avoid being skipped
- **Source:** Friction report — 2026-03-12
- **Guideline:** Roles like Reviewer and Tester get bypassed when there's no visible tracking. Use `taskboard.md` to make their assignments explicit — a task isn't done until the board shows it passed through all required roles.

### Dev environment is prerequisite #1 — establish it before any coding
- **Source:** Friction report v2 — 2026-03-12
- **Guideline:** DevOps must set up a working local development environment (runtime, dev server, browser preview) as the very first task on any project. Without the ability to run code, the Tester role is blocked and the Developer cannot verify their own work. "Can I run this?" must be answered before implementation begins.

### No code is done until it runs — runtime verification is mandatory
- **Source:** Friction report v2 — 2026-03-12
- **Guideline:** Code review catches logic and design issues but misses runtime behavior, browser quirks, and rendering problems. The Developer must verify implementation in a running environment, not just by reading source. The Tester must block and escalate if no runtime exists rather than skip testing.

### The Architect must research tool capabilities before designing around them
- **Source:** Friction report (Playwright) — 2026-03-12
- **Guideline:** When the Architect designs a system that depends on a specific tool (test framework, build tool, library), they must investigate what that tool already provides before designing custom solutions. In the Playwright case, the Architect designed a per-test self-managed server when Playwright's built-in `webServer` config already solved the problem. Use the Researcher for this when the tool is unfamiliar.

### Test infrastructure ownership belongs to DevOps, with Architect input on design
- **Source:** Friction report (Playwright) — 2026-03-12
- **Guideline:** Test infrastructure (config files, test runner setup, server management) is owned by DevOps. When test infrastructure involves design decisions (port strategy, isolation patterns, server lifecycle), DevOps consults the Architect. The Tester writes tests against whatever infrastructure DevOps provides — they do not own the config.

### The Reviewer reviews test code, not just production code
- **Source:** Friction report (Playwright) — 2026-03-12
- **Guideline:** Test code has the same quality bar as production code. The Reviewer must review test files (`test.js`, `test-browser.js`) for correctness, isolation, and completeness. This catches issues like test setup conflicting with the behavior being tested (e.g., `beforeEach` clearing state that a persistence test needs). A test that passes for the wrong reason is worse than no test.

### Time-based games need dev tools from day one
- **Source:** Friction report v3 — 2026-03-12
- **Guideline:** Any game with daily/time-gated mechanics must include dev override tools (reset state, advance day, skip cooldowns) as part of the initial implementation, not as an afterthought. Without these, the Developer cannot verify multi-day behavior and the Tester cannot exercise the full game loop. The DevOps role should flag this during environment setup.

### Rapid iteration still requires self-review on algorithmic changes
- **Source:** Friction report v3 — 2026-03-12
- **Guideline:** When operating in rapid iteration mode (skipping the full role pipeline for speed), the Developer must still self-review any change to core algorithms (RNG, scoring, state management). UI tweaks can skip review safely, but logic changes cannot — the glamour repeat bug and dev button regression both resulted from skipping review on non-UI changes. Rule of thumb: if the change touches a function, not just CSS, pause and review.

### Design docs must update on every code change, not just new features
- **Source:** Friction report v2 — 2026-03-12
- **Guideline:** Bug fixes, redesigns, and visual improvements often produce non-obvious decisions worth documenting as ADRs. The Developer updates design docs as part of implementation; the Documenter verifies this happened. Design docs that only cover initial design quickly become stale.

### Tests must run after every structural change — not just new features
- **Source:** Friction report v4 — 2026-03-12
- **Guideline:** Any change that alters game structure (adding/removing slots, renaming keys, adding script tags, changing state shape) must be followed by running the test suite and fixing failures. Tests that hardcode assumptions about structure (e.g., fixed slot counts, specific CSS classes, regex patterns for script extraction) will silently go stale. The Developer runs tests after implementation; the Tester verifies they still reflect current behavior. A passing stale test is worse than a failing one.

### The Skeptic-only review is the minimum viable gate for fix-chains
- **Source:** Friction report v4 — 2026-03-12
- **Guideline:** The full pipeline (Planner → Architect → Skeptic → Developer → Reviewer → Tester) is appropriate for new features. For fix-chains, bug fixes, and incremental changes, the minimum gate is a Skeptic review after implementation. The Developer implements, the Skeptic reviews for correctness, side effects, and stale assumptions, then the Tester runs tests. Skip the Planner and Architect for work where scope and design are already clear.

### Friction reports are mandatory — plans are optional for sub-feature work
- **Source:** Friction report v4 — 2026-03-12
- **Guideline:** Friction reports have consistently caught more real bugs than plans have prevented: en-dash encoding issues, stale tests, missing migrations, data entry errors, environment problems. Every implementation session must end with a friction report regardless of pipeline mode. Plans are required only for new features or work where scope is ambiguous.

### DevOps must document environment quirks and verify tool compatibility upfront
- **Source:** Friction report v4 — 2026-03-12
- **Guideline:** When the runtime environment has known quirks (e.g., Node.js 24's TypeScript auto-detection breaking data file scripts, Python not installed), DevOps must document these in the project and establish workarounds before they block other roles. The DevOps role should run a brief environment check at session start: verify the runtime, test file I/O with the project's data files, and confirm the dev server works. Discovering environment issues mid-implementation wastes disproportionate time.

### Runtime verification must happen at session end, not just after initial implementation
- **Source:** Friction report v4 — 2026-03-12
- **Guideline:** Unit tests catch logic regressions but cannot verify browser rendering, asset loading, dropdown performance with large datasets, or localStorage migration. At the end of any session that modifies game code, the Developer must verify the game loads and runs in a browser-equivalent environment (headless check at minimum, manual browser check for UI changes). This is separate from the Tester's test suite — it covers the integration surface that tests miss.

### SAST scanning is a mandatory merge gate on all primary branches
- **Source:** User directive — 2026-03-16
- **Guideline:** Every project's CI/CD pipeline must include a SAST scan (e.g., Snyk, Ox Security, Semgrep, Blackduck) as a required check on any PR targeting a primary branch. Merge is blocked on unresolved high or critical findings. DevOps owns the pipeline configuration; the Security Auditor selects the tool, defines severity thresholds, and triages scan output during code review. This gate cannot be skipped or bypassed regardless of timeline pressure.

---

## Format Reference

Each entry follows this structure:

```
### [Short title]
- **Source:** [agent name] — [date]
- **Guideline:** [clear, actionable statement]
```
