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

## Match project

Read adjacent code first. Match naming, formatting, error handling, logging,
config, test patterns. Use utilities already there, never reinvent.

## Smell baseline (Fowler, _Refactoring_ ch.3)

Applies even when repo document nothing. Each is a labelled heuristic
("possible Feature Envy"), never a hard violation. Reads *what it is* -> *fix*:

- **Mysterious Name**: name not reveal what it does or hold. -> rename; no
  honest name coming means design murky.
- **Duplicated Code**: same logic shape in more than one place. -> extract
  shared shape, call from both.
- **Feature Envy**: method reach into another object's data more than own. ->
  move method onto data it envy.
- **Data Clumps**: same few fields or params always travel together. -> bundle
  into one type, pass that.
- **Primitive Obsession**: primitive or string standing in for a domain
  concept. -> give concept its own small type.
- **Repeated Switches**: same switch/if-cascade on same type recurs. ->
  polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change force scattered edits. -> gather
  what changes together into one module.
- **Divergent Change**: one module edited for several unrelated reasons. ->
  split so each change for one reason.
- **Speculative Generality**: abstraction or hooks for needs spec not have. ->
  delete, inline back until real need show.
- **Message Chains**: long `a.b().c().d()` the caller should not depend on. ->
  hide walk behind one method on first object.
- **Middle Man**: class or function that mostly delegate onward. -> cut it,
  call real target direct.
- **Refused Bequest**: subclass ignore or override most of what it inherit. ->
  drop inheritance, use composition.

## Code Naming (engineering artifacts, all languages)

Applies to engineering artifacts: code, tests, commits, diagrams, specs,
tickets. Load it when doing such work.

A name must reveal the thing's purpose to a reader with no other context.
If it only makes sense after reading the design discussion, it is wrong.

- Name the thing, not the mechanism. `controller entity` says how it is
  wired; `projectile` says what it is.
- Name the effect, not the metaphor or process. `change_owner` not
  `grant_control`. `restore_charge` not `handle_charge_event`.
- No scheduling/process words as identity: Deferred, Pending, Delayed,
  Async, Lazy describe when code runs, never what a thing is.
  `DeferredDeliverySystem` -> `ProjectileSystem`.
- No structure filler words as identity: Manager, Controller, Handler,
  Helper, Util, Service*, Data, Info, Object, Item. They describe code
  shape, not purpose. (*Service allowed only under an established
  subsystem convention, e.g. `EntityService`, and the prefix must still
  carry the meaning.)
- Prefer the plain domain word everyone already knows (projectile,
  hitbox, cooldown, teleport) over invented framework jargon. If the
  domain has a common word for it, use that word.
- Constants and fields carry domain + units: `REVIVE_TIME_SEC` not
  `TIME_EPSILON`. `cooldown_remaining` not `timer`.
- Applies everywhere a human reads: classes, members, funcs, signals,
  params, files, diagrams, spec text, commit messages.
- When renaming, rename everywhere in the same change: code, tests,
  diagrams, docs, issue/spec text.

## Scope discipline

Change only what the task names. Architecture, patterns, and interfaces
stay put unless the task says otherwise, and no implied authority to
refactor. Simplification that removes LoC is welcome, but flag WHAT
changed and WHY.

## Ambiguity

Task ambiguous, conflicting with existing patterns, or implying
architecture change -> stop. Unattended agent return BLOCKED
naming the ambiguity.
