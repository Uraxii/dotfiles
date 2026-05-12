<!-- GENERATED FROM .pipeline/_shared/skills/test-path-resolve/SKILL.md — DO NOT EDIT -->
---
name: test-path-resolve
description: Canonical test-path regex set. Reads optional test-paths.txt manifest in run-dir; falls back to default regex set. Use by skeptic + tester for prod-vs-test partitioning + prod-diff-sha.
source: pipeline-native
output-style: caveman:ultra
---

# test-path-resolve

Canonical test-path glob set. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "test-path-resolve", args: "run-dir=<path>")`

OC: `test-path-resolve` custom tool with `{run_dir}` arg.

## Resolution order

1. If `<run-dir>/test-paths.txt` exists → read it. One path-glob per line. Skip empty + `#`-prefixed lines.
2. Else → return default set (below).

## Default glob set

```
**/test_*.py
**/*_test.py
**/tests/**
**/test/**
**/__tests__/**
**/*.test.ts
**/*.spec.ts
**/*.test.tsx
**/*.spec.tsx
**/*.test.js
**/*.spec.js
**/*.test.go
**/*_test.go
**/*Test.java
**/*Tests.java
**/test_*.rb
**/*_spec.rb
**/*Tests.cs
**/*Test.cs
**/test_*.gd
```

## Returns

Newline-separated list of glob patterns.
