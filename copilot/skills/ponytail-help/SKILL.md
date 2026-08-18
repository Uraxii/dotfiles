---
name: ponytail-help
description: "Quick reference for ponytail's modes, skills, and commands. One-shot display."
homepage: https://github.com/DietrichGebert/ponytail
license: MIT
---

# Ponytail Help

Display this reference card when invoked. One-shot, do NOT change mode,
write flag files, or persist anything.

## Levels

| Level | Trigger | What change |
|-------|---------|-------------|
| **Lite** | `/ponytail lite` | Build what's asked, name the lazier alternative in one line. |
| **Full** | `/ponytail` | The ladder enforced: YAGNI → stdlib → native → one line → minimum. Default. |
| **Ultra** | `/ponytail ultra` | YAGNI extremist. Deletion before addition. Challenges requirements before building. |

Level sticks until changed or session end.

## Skills

| Skill | Trigger | What it does |
|-------|---------|--------------|
| **ponytail** | `/ponytail` | Lazy mode itself. Simplest solution that works. |
| **ponytail-review** | `/ponytail-review` | Over-engineering review: `L42: yagni: factory, one product. Inline.` |
| **ponytail-audit** | `/ponytail-audit` | Whole-repo over-engineering audit: ranked list of what to delete. |
| **ponytail-debt** | `/ponytail-debt` | Harvest `ponytail:` shortcut comments into a tracked ledger. |
| **ponytail-gain** | `/ponytail-gain` | Measured-impact scoreboard: less code, less cost, more speed. |
| **ponytail-help** | `/ponytail-help` | This card. |

Copilot has no slash-command layer for skills: it auto-loads a skill when the
prompt matches its description, or you can name the skill directly ("use the
ponytail skill", "ponytail-review this diff"). The `/ponytail ...` forms above
are the mode words to say, not a CLI command.

## Deactivate

Say "stop ponytail" or "normal mode". Resume anytime with `/ponytail`.
`/ponytail off` also works.

## Default Mode

Default is `full`. The upstream plugin's env var / config file
(`PONYTAIL_DEFAULT_MODE`, `~/.config/ponytail/config.json`) are read by its
Claude/Codex hook scripts, which this Copilot port does not ship (see
`ponytail` skill body: no session-start hook here, so nothing auto-activates
or persists a mode flag across turns). Just say the level you want: "ponytail
lite", "ponytail", "ponytail ultra".

## Update

This is a static file copy tracked in the dotfiles repo
(`copilot/skills/ponytail-help/`), not a live plugin install. Refresh it by
re-copying from a newer ponytail release, same as any other skill in this
tree.

## More

Full docs + examples: https://github.com/DietrichGebert/ponytail
