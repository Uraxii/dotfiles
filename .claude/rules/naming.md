# Naming Rule (all projects, all languages)

The cold-reader test governs every name: a reader with ZERO context (never saw
the chat, the docs, the tickets, or the codebase) must understand the thing's
PURPOSE from the name alone. If the name only makes sense after reading the
design discussion, it is wrong.

- Name the THING, not the mechanism. `controller entity` says how it is wired;
  `projectile` says what it is. A cold reader knows what a projectile does.
- Name the EFFECT, not the metaphor or process. `change_owner` not
  `grant_control`. `restore_charge` not `handle_charge_event`.
- No scheduling/process words as identity: Deferred, Pending, Delayed, Async,
  Lazy describe WHEN code runs, never WHAT a thing is. `DeferredDeliverySystem`
  -> `ProjectileSystem`.
- No structure filler words as identity: Manager, Controller, Handler, Helper,
  Util, Service*, Data, Info, Object, Item. They describe code shape, not
  purpose. (*Service allowed only under an established subsystem convention,
  e.g. `EntityService`, and the prefix must still carry the meaning.)
- Prefer the plain domain word everyone already knows (projectile, hitbox,
  cooldown, teleport) over invented framework jargon. If the domain has a
  common word for it, use that word.
- Constants and fields carry domain + units: `REVIVE_TIME_SEC` not
  `TIME_EPSILON`. `cooldown_remaining` not `timer`.
- The explain test: if introducing the name requires a sentence of definition
  before anyone can follow ("the controller entity is the thing that..."),
  rename it to that sentence's subject.
- Applies everywhere a human reads: classes, members, funcs, signals, params,
  files, diagrams, spec text, commit messages.
- When renaming, rename EVERYWHERE in the same change: code, tests, diagrams,
  docs, issue/spec text. A half-renamed concept is worse than a badly named one.
