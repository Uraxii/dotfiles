---
name: excalidraw-diagrams
description: House standard for drawing diagrams through the claude.ai Excalidraw MCP connector — 4:3 camera sizes, font and element sizing, spacing, color palette, contrast, drawing order, dark mode. ALSO covers embedding diagrams in an Obsidian vault (.excalidraw.md), which has extra hard constraints (8-char ids, static geometry, headless verify). Use when creating or editing an Excalidraw diagram, or when asked for a flowchart, architecture diagram, sequence diagram, state chart, or any visual drawn via create_view or embedded in Obsidian. Load before drawing so the output follows the sizing/spacing/color conventions.
---

# Excalidraw Diagrams

Rules for diagrams drawn via the Excalidraw MCP connector. The diagram renders
inline at ~700px wide — design for that constraint.

## First steps

1. Call `mcp__claude_ai_Excalidraw__read_me` once per conversation for the full
   element-format reference (JSON shape of rectangles, arrows, labels, camera,
   delete, checkpoints, animation). It is the source of truth for the format.
2. Then draw with `mcp__claude_ai_Excalidraw__create_view`, following the house
   standards below. These pin the sizing/spacing/color conventions; when they and
   the read_me agree, either is fine; where a specific project documents its own
   diagram standard, that project wins.

## Targeting Obsidian (embedded `.excalidraw.md`)

The MCP connector is a LIVE renderer; the Obsidian Excalidraw plugin is a STATIC
one. These rules ONLY apply when the diagram must live in an Obsidian vault.
Ignoring any of them corrupts the file.

1. **Element ids MUST be exactly 8 alphanumeric chars.** Obsidian's own ids are
   `nanoid(8)`. Its `## Text Elements` parser only matches 8-char anchors
   (`/\s\^(.{8})[\n]+/`) and regenerates any text id whose length != 8. A
   non-8-char id → parser matches nothing → the next open+autosave dumps the raw
   `## Text Elements` (anchors and all) into the shapes and duplicates entries.
   Use deterministic `sha1(name)[:8]`. This is the #1 corruption cause.
   - Corollary: NEVER open a non-conforming file in Obsidian to "check" it — the
     open+autosave corrupts it in place. Verify headlessly (rule 5).
2. **Bake FINAL static geometry — live-snap does not survive export.** MCP snaps
   arrows onto edges and auto-fits text as you draw; Obsidian draws the stored
   points verbatim and never recomputes. `read_checkpoint` returns your RAW
   authored points, not the snapped ones. So arrow start/end points must
   physically terminate ON the target box edges, and boxes must be sized to fit
   their text. Do not rely on Obsidian re-snapping.
3. **`## Text Elements` must be symmetric with the JSON.** Every text element ↔
   one `^id` anchor; anchor-set == text-id-set; no duplicates. Bound labels are
   SEPARATE text elements with `containerId` + the container's `boundElements`
   back-ref. Collapse `\n{2,}` → `\n` inside labels (embedded blank lines
   fragment the parser).
4. **Prefer a generator that emits static geometry over the MCP→plugin round-trip.**
   The round-trip copies non-static geometry and corrupts easily. Author vault
   diagrams with code that computes edge-accurate arrows, text-fit boxes, and
   8-char ids. (project_e: `90 Meta/tools/excalidraw_gen.py`;
   `normalize_excalidraw_ids.py` stabilizes existing/hand-authored files.)
5. **Verify renders HEADLESS — never on the user's screen.** You cannot see
   Obsidian's render otherwise, and opening files there corrupts non-conforming
   ones. Recipe: extract the ```json``` Drawing block → `scene.excalidraw` →
   `npx excalidraw-brute-export-cli -i scene.excalidraw -o out.png -f png -b true -s 2`
   (headless Chromium — same engine/font as Obsidian, zero display use), then Read
   the PNG. No node/Chromium on the host (immutable OS)? Run it in a container
   (distrobox/toolbox). Drive the user's live Obsidian GUI only with explicit
   consent — never on their primary display by default (a naive `obsidian://` /
   `notesmd-cli open` pops their screen and, via autosave, corrupts a
   non-conforming file). Never use the user's eyes as the render loop.

### Workflow (Obsidian-embedded)

Verify BEFORE Obsidian ever opens the file — that is the whole game.

1. Author with a generator (rule 4), not the MCP round-trip.
2. Static-check every id is 8-char alphanumeric and `## Text Elements` is
   symmetric (rules 1, 3) — before the vault sees the file.
3. Headless-render and Read the PNG to check layout (rule 5). Iterate HERE.
4. Only a file that passed 2–3 is safe to open in the vault.

### Layout conventions (house style)

- Decision trees / flows fan OUT: wide column spread, generous gaps, branches
  diverge outward — not cramped or converging.
- Branch arrows link to the box TOP (arrowhead drops straight down into
  top-center), not the inner side.
- Edge conditions (YES/NO, labels) are BOUND ARROW LABELS on the line, not
  floating text beside it.

## Camera (4:3 aspect ONLY)

Emit a `cameraUpdate` as the FIRST element. Use ONLY these sizes:

| Cam | width x height | Use | Min readable font |
|-----|----------------|-----|-------------------|
| S   | 400 x 300  | close-up, 2-3 elements | 16 |
| M   | 600 x 450  | one section | 16 |
| L   | 800 x 600  | standard full diagram (DEFAULT) | 16 |
| XL  | 1200 x 900 | large overview | 18 |
| XXL | 1600 x 1200| panorama / final overview | 21 |

- Non-4:3 viewports distort. Never use another ratio.
- Leave padding: don't match camera size to content size (500px content -> 800x600 cam).
- Emit the `cameraUpdate` BEFORE the content it frames; use several to pan/zoom and guide attention (users love it).

## Fonts

- Body / labels / descriptions: min fontSize **16**.
- Titles / headings: min fontSize **20**.
- Secondary annotations only: min **14** (sparingly). Never below 14. Honor per-camera minimums (XL >= 18, XXL >= 21).

## Element sizing & spacing

- Min shape size **120 x 60** for labeled rectangles / ellipses.
- Min **20-30px** gaps between elements.
- Prefer fewer, larger elements over many tiny ones.
- Check y-coordinates so boxes, labels, and text don't overlap.
- Prefer labeled shapes (`"label": { "text": ... }`) over separate text elements; text auto-centers, container auto-resizes, saves tokens.

## Colors

### Primary (strokes, data series)
| Name | Hex | Use |
|------|-----|-----|
| Blue | `#4a9eed` | Primary actions, links, series 1 |
| Amber | `#f59e0b` | Warnings, highlights, series 2 |
| Green | `#22c55e` | Success, positive, series 3 |
| Red | `#ef4444` | Errors, negative, series 4 |
| Purple | `#8b5cf6` | Accents, special, series 5 |
| Pink | `#ec4899` | Decorative, series 6 |
| Cyan | `#06b6d4` | Info, secondary, series 7 |
| Lime | `#84cc16` | Extra, series 8 |

### Pastel fills (shape backgrounds)
| Color | Hex | Good for |
|-------|-----|----------|
| Light Blue | `#a5d8ff` | Input, sources, primary nodes |
| Light Green | `#b2f2bb` | Success, output, completed |
| Light Orange | `#ffd8a8` | Warning, pending, external |
| Light Purple | `#d0bfff` | Processing, middleware, special |
| Light Red | `#ffc9c9` | Error, critical, alerts |
| Light Yellow | `#fff3bf` | Notes, decisions, planning |
| Light Teal | `#c3fae8` | Storage, data, memory |
| Light Pink | `#eebefa` | Analytics, metrics |

### Background zones (use `opacity: 30`)
| Color | Hex | Good for |
|-------|-----|----------|
| Blue zone | `#dbe4ff` | UI / frontend layer |
| Purple zone | `#e5dbff` | Logic / agent layer |
| Green zone | `#d3f9d8` | Data / tool layer |

## Contrast (critical)

- Text on white: never light gray. Minimum text color `#757575`.
- Colored text on light fills: use dark variants (`#15803d` not `#22c55e`, `#2563eb` not `#4a9eed`).
- White text needs a dark background.
- No emoji in text — they don't render in Excalidraw's font.

## Drawing order

- Array order = z-order (first = back, last = front).
- Emit progressively: background zone -> shape -> its label -> its arrows -> next shape. Not all-shapes-then-all-text.
- Draw decorative art/icons LAST.

## Dark mode (only if asked)

First element (before `cameraUpdate`) = a huge dark bg rectangle (~10x camera, e.g. 10000x7500) at `#1e1e2e`. Then: text `#e5e5e5` primary / `#a0a0a0` muted; fills `#1e3a5f` blue, `#1a4d2e` green, `#2d1b69` purple, `#5c3d1a` orange, `#5c1a1a` red, `#1a4d4d` teal; primary palette colors for strokes/arrows.
