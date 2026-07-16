---
name: excalidraw-diagrams
description: House standard for drawing diagrams through the claude.ai Excalidraw MCP connector — 4:3 camera sizes, font and element sizing, spacing, color palette, contrast, drawing order, dark mode. Use when creating or editing an Excalidraw diagram, or when asked for a flowchart, architecture diagram, sequence diagram, state chart, or any visual drawn via create_view. Load before drawing so the output follows the sizing/spacing/color conventions.
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
