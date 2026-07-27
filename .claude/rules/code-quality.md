# Code Quality Rule (all languages, all vendors)

Load before writing or changing code. Repo's own documented standard always
override this file. Skip anything the repo's tooling already enforce.

## Hard limits

- Function <=40 LoC. File <=600 LoC, one cohesive responsibility.
- Line <=80 chars (<=100 when readability win).
- Explicit return types. Function contracts stated.
- No bare catch/except. Handle errors explicit, per surrounding context.
- No magic numbers. Named constants carry domain + units.
- Guard clauses over deep nesting. Nesting >3 -> extract function.
- Compute or mutate, never both in same function.
- YAGNI. No dependency added without explicit approval.

## Match the project

Read adjacent code first. Match naming, formatting, file organization, and the
established patterns for error handling, logging, config, and tests. Use the
utilities and abstractions already there. Comments explain non-obvious logic or
business rules, nothing else.

## Smell baseline (Fowler, _Refactoring_ ch.3)

Applies even when repo document nothing. Each is a labelled heuristic
("possible Feature Envy"), never a hard violation. Reads *what it is* -> *fix*:

- **Mysterious Name** — name not reveal what it does or hold. -> rename; no
  honest name coming means design murky.
- **Duplicated Code** — same logic shape in more than one place. -> extract
  shared shape, call from both.
- **Feature Envy** — method reach into another object's data more than own. ->
  move method onto data it envy.
- **Data Clumps** — same few fields or params always travel together. -> bundle
  into one type, pass that.
- **Primitive Obsession** — primitive or string standing in for a domain
  concept. -> give concept its own small type.
- **Repeated Switches** — same switch/if-cascade on same type recurs. ->
  polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change force scattered edits. -> gather
  what changes together into one module.
- **Divergent Change** — one module edited for several unrelated reasons. ->
  split so each change for one reason.
- **Speculative Generality** — abstraction or hooks for needs spec not have. ->
  delete, inline back until real need show.
- **Message Chains** — long `a.b().c().d()` the caller should not depend on. ->
  hide walk behind one method on first object.
- **Middle Man** — class or function that mostly delegate onward. -> cut it,
  call real target direct.
- **Refused Bequest** — subclass ignore or override most of what it inherit. ->
  drop inheritance, use composition.

## Scope discipline

Change only what the task name. Architecture, patterns, and interfaces stay put
unless the task say otherwise. Simplification that remove LoC is welcome, but
flag WHAT changed and WHY.

## Before delivering

1. Score your own solution out of 5. Below 5 -> iterate until genuinely
   shippable.
2. Confirm no scope creep against the exact task.
3. Confirm style match adjacent files.
4. Confirm comments add value, not noise.
5. Confirm no architectural change slipped in.

## Ambiguity

Task ambiguous, conflicting with existing patterns, or implying architecture
change -> stop. Interactive agent ask. Unattended agent (Codex) return BLOCKED
naming the ambiguity. Never guess. Never assume implied authority to refactor.
