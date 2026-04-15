# GNU Stow Skill

IMPORTANT: Follow these rules when managing symlinks via GNU Stow.

## Core Concepts

- **Stow directory**: contains packages (default: current dir)
- **Target directory**: where symlinks land (default: parent of stow dir)
- **Package**: subtree inside stow dir whose structure mirrors target
- Stow creates symlinks in target that point back to package files

## Commands

```bash
# Stow package into target
stow -t <target> <package>

# Unstow (remove symlinks)
stow -D -t <target> <package>

# Restow (unstow + stow — use after restructuring)
stow -R -t <target> <package>

# Dry run (simulate, no changes)
stow -n -v -t <target> <package>

# Adopt existing files (move target files into package, replace w/ symlinks)
stow --adopt -t <target> <package>

# Verbose output (stackable: -vv, -vvv)
stow -v -t <target> <package>
```

## Flat Mode (Single Package)

When repo root IS the package, use `.` as package name:
```bash
stow -t ~ .
```

## Ignore Files

- **`.stow-local-ignore`** — per-package regex patterns, prevents matched files from being symlinked
- **`.stow-global-ignore`** — `~/.stow-global-ignore`, applies to all packages
- Default ignores (when no ignore file exists): `.git`, `.gitignore`, `README.*`, `LICENSE.*`
- Custom ignore file overrides defaults — must re-add defaults if needed

## Conflict Resolution

- Conflict = real file/dir exists at target where symlink would go
- `--adopt`: moves target file into package, replaces w/ symlink. **Destructive to package state** — always diff after
- Alternative: backup target file, delete, restow

## Rules

- Never create symlinks manually — stow manages all symlinks
- Always dry-run (`stow -n -v`) after structural changes or ignore file edits
- Always restow (`stow -R`) after moving/renaming files in package
- Stale symlinks from old paths require manual cleanup after moves
