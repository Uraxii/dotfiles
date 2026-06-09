# Skeptic Gate Rule (generalized, all work)

- The implementor is not trusted to self-certify. Risky or
  high-consequence work gets an independent `skeptic-gate` challenge
  check before it ships (before PR open / integration / merge).
- Applies to all work, every project — not one repo. Orchestrating via
  tech-lead auto-delegates it; working solo, invoke it yourself before
  shipping risky changes.
- Trigger: architecture; security / trust boundaries; netcode / state /
  replication; migrations / deletes / irreversible ops; public API or
  schema; large cross-cutting changes; weak, missing, or unexecuted
  verification; or tests-pass-but-suspicious. Skip: small mechanical or
  docs-only edits.
- It reads the real diff, not a summary, and returns one of
  `PASS | BLOCK | NEEDS_TEST | NEEDS_ARCH_REVIEW | NEEDS_REQUIREMENTS`.
  A non-PASS halts delivery until resolved; re-run after fixes.
- It is read-only and writes no files — it reports its verdict, the same
  way the other agents report results.
