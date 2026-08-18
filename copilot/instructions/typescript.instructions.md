---
applyTo: "**/*.ts,**/*.tsx"
description: TypeScript coding rules (strictness, typing idioms).
---

# TypeScript Rules

- `strict: true` in tsconfig. No `any` w/o comment justifying (bare,
  external data, or generic constraints); prefer `unknown`, validate at boundary.
- No `!` non-null assertion w/o comment why safe.
- `const` default. `let` only when reassigned. Never `var`.
- Discriminated unions over type casting for narrowing.
- No `enum`, use `as const` objects or union literal types.
- Async: always handle rejection. No floating promises.
- Named imports over default (refactor-safe).
- No `Object`, `Function`, `String`, use lowercase primitives.
- `readonly` on properties that shouldn't mutate.
- No `delete` operator, restructure or use `Map`.
- Zod/valibot at API boundaries. No trust of external shape.
- `satisfies` over `as` when asserting type compatibility.
- Nullish coalescing (`??`) over logical OR (`||`) for defaults.
