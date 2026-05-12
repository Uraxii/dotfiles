---
name: test-path-resolve
description: Canonical test-path regex set. Reads optional test-paths.txt manifest in run-dir; falls back to default regex set. Use by skeptic + tester for prod-vs-test partitioning + prod-diff-sha.
disable-model-invocation: true
source: pipeline-native
output-style: caveman:ultra
---

# test-path-resolve

Canonical test-path glob set. Pipeline-internal.

## Invocation

```
Skill(skill: "test-path-resolve", args: "run-dir=<path>")
```

Returns list of glob patterns.

## Resolution order

1. If `<run-dir>/test-paths.txt` exists → read it. One path-glob per line. Skip empty + `#`-prefixed lines. Return list.
2. Else → return default set (below).

## Default regex/glob set

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
**/*Test.cs
**/*Tests.cs
**/test_*.gd
**/*.spec.*
**/cypress/**
**/e2e/**
**/integration-tests/**
**/playwright/**
**/.github/**
```

## Build manifest override

Build agent MAY emit `<run-dir>/test-paths.txt` to override default set for unlisted ecosystems or project-specific layouts. One path-glob per line.

## Used by

- skeptic: shard scope-check, prod-vs-test partitioning
- tester: test-only revision routing
- prod-diff-sha skill: exclude test paths from prod diff

## Don't

- No directory scanning. Globs only.
- No project-CLAUDE.md inference (test path = build-emitted manifest or default).
