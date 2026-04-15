# Pipeline Context: {task-slug}

> Created: {date} | Pipeline: {pipeline_id} | Status: {In Progress|Complete}

**Conventions:**
- Each role appends when done. Skip sections for roles not in your mode.
- On revision (Skeptic rejects → role reworks): **overwrite** your section, don't duplicate.
- Skeptic + Security Auditor run concurrently post-Developer (Orchestrator spawns both). Each appends independently.
- After Monitor processes, completed pipeline contexts can be deleted/archived.

---

## Planning

**Scope:** {one-sentence description}

**Tasks:**
- {task 1 — acceptance criteria}
- {task 2 — acceptance criteria}

**Sequencing:** {dep order, parallelizable work}

**Downstream notes:** {what Architect/Developer needs}

---

## Architect

**Design decisions:**
- {decision — choice + why}

**File structure:**
- {path → purpose}

**API contracts / interfaces:**
- {interface}

**Downstream notes:** {what Developer needs}

---

## Skeptic

**Verdict:** {Approved | Revise | Rejected}

**Conditions:** {any approval conditions}

**Objections addressed:** {what was raised + resolved}

---

## Developer

**Files changed:**
- {path — what + why}

**Decisions made during impl:**
- {decision — why diverged from/extended design}

**Known issues:** {what Tester should target}

**Downstream notes:** {what Reviewer/Tester needs}

---

## Skeptic (code review)

**Verdict:** {Approved | Changes requested}

**Issues found:**
- {blocking|suggestion|nit}: {description}

---

## Security Auditor

**Verdict:** {Approved | Changes requested}

**Issues found:**
- {blocking|suggestion|nit}: {description}

---

## Tester

**Test results:** {X/X passed}

**Failures:** {description, repro steps}

**Coverage gaps:** {untested areas}

---

## Friction Report

**What went wrong:** {friction points}

**Memory updates:**
- Role memory: {what was written where}
- Project memory: {what was written where}
