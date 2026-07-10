# Progress Tracking Reference

Every quiz is tracked. Progress lives in a per-subject **Mastery DB** in the user's Notion: one
row per atomic item, carrying state. The DB doubles as the subject's syllabus — selection weights
over the full item pool. Tracking is generic; nothing here is tied to one subject.

## Where practice lives

All practice sits under a single workspace-root page **"Practice Quizzes"** (separate from any
reference knowledge base), with one **sub-page per subject**. Each subject sub-page holds that
subject's Mastery DB and its dated quiz pages:

```
Practice Quizzes (root)
└── <Subject>           e.g. ASVS
    ├── <Subject> Mastery (DB)
    └── Quiz — YYYY-MM-DD ...
```

Never nest practice inside the user's reference knowledge base.

## Subject registry (resolve exactly)

Under "Practice Quizzes" is a **Subjects** registry database — one row per subject — that pins
each subject to exact ids and its profile. Resolve subjects through the registry, not by guessing
page names.

Find the registry once (`notion-search` "Subjects", under "Practice Quizzes"), then query its
data source:
`SELECT "Subject","Mastery","Subject page","Source","Persona","Mission","Item scheme","Question types" FROM "collection://<registry-ds>"`.

Each row gives everything needed. Note: `Mastery` and `Subject page` are stored as Notion
**mentions** (live links), not bare ids — parse the id out of the tag before using it.
- `Mastery` — a `<mention-data-source url="collection://<id>"/>` for the subject's Mastery data
  source. Extract `collection://<id>` from the tag; query/upsert against it.
- `Subject page` — a `<mention-page url="https://app.notion.com/p/<id>"/>` for the subject
  sub-page. Extract the page id from the tag; create new quiz pages under it.
- `Source` — where content comes from (the user's Notes DB, a page, a project doc, web).
- `Persona` — teacher persona/level/framing for Step 1.
- `Mission` — WHY the user is learning this subject (the real-world reason, not the topic).
  Ground every plan, quiz framing, and next-topic pick in it. Empty or stale → ask the user
  before generating; missions change as skills grow — confirm, then update the row. A legacy
  row without the property → backfill it on first use.
- `Item scheme` — the stable item-id format (e.g. `ASVS 5.3.2`).
- `Question types` — which styles apply (remaps non-code subjects). JSON array.

**New subject (no row yet):** set it up once — create the subject sub-page under "Practice
Quizzes", create its `<Subject> Mastery` DB under that sub-page, then add a registry row with the
then add a registry row with the profile and the resolved `Mastery` and `Subject page` written
as **mentions** — `<mention-data-source url="collection://<id>"/>` and
`<mention-page url="https://app.notion.com/p/<id>"/>` respectively — so the registry stays a graph
of live links, not opaque ids. After that, resolution is always exact.

## Mastery DB (per subject)

The registry row's `Mastery` mention resolves to the data source to query and upsert. You only create a Mastery
DB when setting up a brand-new subject — under that subject's sub-page, with this generic schema,
then record its id in the registry. Generic schema:
  ```
  CREATE TABLE (
    "Item" TITLE,
    "State" SELECT('weak':red,'learning':yellow,'solid':green,'unseen':gray),
    "Seen" NUMBER, "Correct" NUMBER,
    "Last result" SELECT('correct':green,'partial':yellow,'missed':red,'dontknow':orange),
    "Review soon" CHECKBOX, "Last seen" DATE,
    "Section" RICH_TEXT, "Level" RICH_TEXT, "Label" RICH_TEXT
  )
  ```
  `Item` = the stable id (e.g. `ASVS 5.3.2`). `Section` = chapter/group. `Level` optional.
  `Label` = short human name.
- **Seed the syllabus.** For a structured KB, rows can be created lazily as items are quizzed,
  or pre-seeded from the KB's item list. For a frozen-syllabus subject, pre-seed every item as
  `unseen` so weighting sees the whole pool from day one.

## Weakness-weighted selection (GENERATE)

Read the DB:
`SELECT "Item","State","Seen","Correct","Review soon" FROM "collection://<ds>"`.
Pick 6-8 items, honoring any focus the user named. Selection targets the **zone of proximal
development** (see `pedagogical-principles.md` #13): the hardest items the user can handle with
support, biased toward what the subject's `Mission` needs next. Weight:
- `weak` / `unseen` / `Review soon` checked → often.
- `learning` → sometimes.
- `solid` → rarely, and at a harder (higher-level) framing so staying solid means handling it.
Don't repeat the previous quiz's items.

## Grade and upsert (GRADE)

`notion-fetch` the quiz page: typed answers after each `Your answer:`, ticked options as `[x]`,
the per-question `[x] Not Sure` flag, and the answer key in the `<details>`
block.

Mark each (see `format-quizzes.md`): mcq/multi against the key (partial credit for multi);
free-text against the rubric, quoting earned/missed points. A **blank** answer = a gap → teach it
fully, mark `weak` (or `dontknow`), prioritize it. A ticked **Not Sure** means they guessed: score
the answer normally (correct/partial/missed) but set `Review soon` and don't promote past
`learning` this attempt, whatever the result.

State transitions per item:
- full credit → `unseen`/`weak` → `learning`; `learning` → `solid` after ~2 consecutive
  full-credit results that were **not** marked Not Sure.
- partial → `learning`.
- missed or dontknow (blank) → `weak`, check `Review soon`.
- **Not Sure modifier:** on any Not Sure tick, set `Review soon` and cap this attempt at `learning`
  (a Not Sure full-credit does not count toward the consecutive total for `solid`).
- a `solid` item missed on a harder re-test → back to `learning`.
Always increment `Seen`; increment `Correct` only on full credit; set `Last result` and
`Last seen` (today).

Upsert: query the DB for the covered items by `Item`; `notion-update-page` the existing rows,
`notion-create-pages` the missing ones (parent = the data source). Numbers are JS numbers;
checkbox `__YES__`/`__NO__`; date via the expanded `date:Last seen:start` key.

## Feedback write-back

Append a `Results — YYYY-MM-DD` callout/toggle to the quiz page and summarize in chat: per-item
reveal + objective, depth on gaps (control/concept, common mistake, idiomatic fix in the
relevant language, the senior layer), a solid-vs-review summary, and what resurfaces next.
