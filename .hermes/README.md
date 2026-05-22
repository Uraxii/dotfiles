# Hermes Agent harness — pipeline port

Port of the Claude Code multi-role gated pipeline to the Hermes Agent harness
(Nous Research, `https://hermes-agent.nousresearch.com`). Parallel coexistence
with `~/dotfiles/.claude/` — same `.pipeline/runs/<artifact-id>/` ledger.

Source-of-truth: this dotfiles repo. Stow symlinks the repo-versioned subtree
into `$HOME/.hermes/`. Secrets + runtime state are stow-ignored.

## Layout

```
.hermes/
├── README.md                          # this file
├── SOUL.md.example                    # template — user copies to ~/.hermes/SOUL.md (stays local)
├── config.yaml.example                # template — user copies to ~/.hermes/config.yaml (stays local)
├── skills/
│   ├── pipeline/                      # 11 role-skills (orchestrator + 10 roles)
│   ├── pipeline-agent-brief-format/   # 4 prompt-skills
│   ├── pipeline-handoff-doc/
│   ├── pipeline-decision-elicitation/
│   ├── pipeline-agent-preflight/
│   └── caveman/                       # output-style skill
├── skill-bundles/
│   └── pipeline.yaml                  # /pipeline entry point
├── plugins/
│   └── pipeline-core/                 # Python plugin — 8 logic tools
├── hooks/
│   ├── cap_bash_timeout.py            # shell hook
│   ├── graphify_advice.sh             # shell hook
│   ├── terminal_policy.py             # shell hook (allow/deny)
│   └── role_policy.py                 # shell hook (per-role path denylist)
├── policy.json                        # terminal_policy allow/deny patterns
├── role-policy.json                   # role_policy per-role denylists
└── (runtime + local — stow-ignored + gitignored, live in $HOME only):
    ├── SOUL.md                        # local-only; seed from SOUL.md.example
    ├── config.yaml                    # local-only; seed from config.yaml.example
    ├── .env                           # secrets: ANTHROPIC_API_KEY, DISCORD_*
    ├── state.db                       # SQLite session store
    ├── sessions/sessions.json         # routing index
    ├── memory/                        # Hermes memory provider state
    └── pipeline-registry.json         # active-run registry
```

## Seeding the local-only files

`SOUL.md` and `config.yaml` are **not stowed**. Hermes writes / owns these on the host. Seed them once from the repo templates:

```bash
mkdir -p ~/.hermes
cp ~/dotfiles/.hermes/SOUL.md.example ~/.hermes/SOUL.md
cp ~/dotfiles/.hermes/config.yaml.example ~/.hermes/config.yaml
```

Or, if Hermes already wrote its own defaults to `~/.hermes/SOUL.md` and `~/.hermes/config.yaml`, diff the templates against them and merge the pipeline-specific blocks (hooks, plugins.enabled, terminal.backend lock, delegation limits).

## Boot

1. `hermes plugins enable pipeline-core` + restart hermes.
2. `hermes config set` for `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, etc.
3. `hermes chat` → `/pipeline <request>`.

See `docs/tooling.md` for full setup + decision-router sentinel formats.
