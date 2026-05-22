# TypeScript Rules

- `strict: true` in tsconfig. No `any` w/o comment justifying.
- No `!` non-null assertion w/o comment why safe.
- `const` default. `let` only when reassigned. Never `var`.
- Discriminated unions over type casting for narrowing.
- `unknown` over `any` for external data. Validate at boundary.
- No `enum` — use `as const` objects or union literal types.
- Async: always handle rejection. No floating promises.
- Named imports over default (refactor-safe).
- No `Object`, `Function`, `String` — use lowercase primitives.
- `readonly` on properties that shouldn't mutate.
- No `delete` operator — restructure or use `Map`.
- Zod/valibot at API boundaries. No trust of external shape.
- `satisfies` over `as` when asserting type compatibility.
- Nullish coalescing (`??`) over logical OR (`||`) for defaults.
- No `any` in generic constraints — use `unknown` or specific bound.
