# Hermes Agent harness

This subtree stores repo-versioned Hermes profile prompts, skills, skins, and hooks that are safe to stow into `$HOME/.hermes/`.

## Current stance

- Pipeline port removed.
- Profile prompts mirror `https://github.com/omerxx/dotfiles/tree/master/opencode/agent`.
- Default `.hermes/SOUL.md` mirrors upstream `tech-lead.md`.
- Reusable non-pipeline skills such as `caveman` remain.
- Graphify hook remains because repo `AGENTS.md` owns graphify usage policy.

## Layout

```text
.hermes/
├── SOUL.md                    # default prompt, mirrored from omerxx tech-lead
├── profiles/*/SOUL.md         # omerxx agent prompts as Hermes profiles
├── skills/caveman/            # output-style skill
├── hooks/graphify_advice.sh
└── skins/
```

Local runtime files (`config.yaml`, `.env`, `state.db`, sessions, memory) live in `$HOME/.hermes/` and should not be committed.
