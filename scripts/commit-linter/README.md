# commit-linter

A local git pre-commit hook for this dotfiles repo. Purpose: this repo is
public, so no machine- or user-identifying value, and no secret, should
ever land in a commit.

The hook is installed at `.git/hooks/pre-commit` (local, untracked, not
part of this repo's tracked files). It is a thin wrapper that calls the
real script here:

```
scripts/commit-linter/lint_staged.py
```

Python 3, standard library only -- no third-party packages, no venv. The
required external binary is `trufflehog` (pass 6, see below); `git` itself
is assumed. Pass 7 can also use StepSecurity Dev Machine Guard when
installed. It was a bash script
(`spikes/commit-linter/lint-staged.sh`) until the repo adopted the rule
that nothing under `spikes/` is ever committed; the port is
behaviour-for-behaviour, same passes, same messages, same exit codes.

Keeping the logic in a tracked file means it can be reviewed and improved
like normal code, while the hook installation itself stays local per
machine (as git hooks always are).

## What it catches

Only the STAGED content of staged files is scanned, i.e. exactly what
would be committed. Working-tree-only or untracked changes are never
touched.

1. **Partial staging.** If a staged file also has unstaged changes on
   disk (the index and working tree disagree), the hook refuses to
   rewrite it silently. It blocks the commit and asks you to stage the
   whole file or none of it.
2. **Secret-shaped strings.** Hard blocked, never auto-fixed: known API key
   prefixes, private key headers, and any `*_KEY` / `*_TOKEN` /
   `*_SECRET` assignment to a long base64-ish value. Exempt:
   `*_STORAGE_KEY` / `*_CACHE_KEY` / `*_COOKIE_NAME` constants assigned a
   plain lowercase kebab/snake value (no uppercase, no `+`/`/`/`=`) --
   these are storage/cookie key names, not secrets. TruffleHog (pass 5)
   still scans them.
3. **Identity values with no portable form** are hard-blocked, not
   rewritten:
   - `<your-email>`
   - `<your-tailnet-id>` (covers `*.<your-tailnet-id>.ts.net` hosts too)
   - the machine hostname, read live via `socket.gethostname()` at hook
     run time (never hardcoded, so this still works if the machine is renamed)

   The email and tailnet id are loaded at hook run time from
   `scripts/commit-linter/identity.local` (see "Identity config" below),
   never hardcoded in this script or this doc.
4. **Expanded home paths and bare username in path-like contexts.** Real
   home directories after shell expansion are auto-replaced with a portable
   form (see standard below). The local username is replaced with `$USER`
   only when it sits next to a `/` or `@` (e.g. `~/media/$USER/`,
   `$USER@host`).
5. **Bare username anywhere else.** After pass 4 has auto-fixed portable
   path and login contexts, any remaining bare username is hard-blocked,
   never auto-fixed. Replace it with `$USER`, or move the value into
   `scripts/commit-linter/identity.local` if it is identity config.
6. **Everything TruffleHog's 750+ detectors know about.** Runs after the
   five checks above, as a second, independent layer. Any finding blocks
   the commit; nothing is ever auto-fixed.
7. **StepSecurity Dev Machine Guard supply-chain scan.** If installed, runs
   after TruffleHog and blocks on CRITICAL/HIGH findings. On a clean run it
   prints `dev-machine-guard: clean` to stdout. If absent, this optional
   pass skips silently and never blocks.

## Identity config

The email and tailnet id checked by pass 3 are not hardcoded anywhere
tracked. They live in `scripts/commit-linter/identity.local`, a
per-machine file already covered by this repo's blanket `*.local`
gitignore rule:

```
EMAIL='<your-email>'
TAILNET='<your-tailnet-id>'
```

The hook PARSES this file (two `KEY=value` shell assignments, `#`
comments allowed) if it exists; it never `source`s or execs it. A
missing file (a fresh clone, another machine, CI) is normal, not an
error: the hook prints a one-line note and skips those two needles,
while the hostname check and every other pass still run. Create the
file once per machine with your real values to get the email/tailnet
block back.

## Self-exemption for the linter itself

`scripts/commit-linter/lint_staged.py` contains the secret prefixes and the
`_KEY`/`_TOKEN`/`_SECRET` pattern as regex source, so it legitimately
contains the trigger text without containing a real leak. Left unexempted,
the hook blocked the script on its first real commit.

Only that script is exempt from the secret regex (pass 2), auto-fix
(pass 4), and bare-username block (pass 5). The README is not exempt. Pass 3
(identity-value block) does not need an exemption for tracked files because
the email and tailnet id live in `identity.local`. The script is NOT exempt
from TruffleHog (pass 6): a real secret pasted into it still blocks the
commit.

## TruffleHog layer

Installed user-scope, no sudo, no docker:

```
curl -sL -o trufflehog.tar.gz \
  https://github.com/trufflesecurity/trufflehog/releases/download/v3.95.9/trufflehog_3.95.9_linux_amd64.tar.gz
tar xzf trufflehog.tar.gz trufflehog
mv trufflehog ~/.local/bin/trufflehog
chmod +x ~/.local/bin/trufflehog
```

Version installed: `trufflehog 3.95.9` (checksum verified against the
release's published `trufflehog_3.95.9_checksums.txt`).

Uninstall:

```
rm ~/.local/bin/trufflehog
```

**Invocation and why.** TruffleHog's own pre-commit example
(`trufflehog git file://. --since-commit HEAD ...`) scans commit
history, which does not exist yet for what is currently staged. To
scan exactly the staged content, the hook copies each staged file's
index blob (`git show ":file"`) into a scratch directory, then runs:

```
trufflehog filesystem <scratch-dir> --no-update \
  --results=verified,unverified,unknown --json
```

`--results` is set explicitly and includes `unverified`: testing in the
throwaway repo showed most fake-but-real-shaped test secrets (no live
credential behind them) come back as `Verified: false`, i.e.
`unverified`. The docs' typical example (`--results=verified,unknown`)
would have silently let those through, so it was not used. This was
proven, not assumed: see test 8 below.

**Fail-closed.** If `trufflehog` is not on `PATH` at commit time, the
hook blocks the commit with a one-line hint pointing at this README,
instead of skipping the scan. A missing scanner must never look like a
clean scan.

**Speed.** Staged-only scope keeps it fast: a typical single-file
commit measured consistently around 3.6 to 4.0 seconds wall time in
testing (most of that is TruffleHog's own startup and detector-init
cost, not file count).

## StepSecurity Dev Machine Guard layer

Pass 7 is an optional StepSecurity Dev Machine Guard supply-chain scan.
The linter invokes `~/.local/share/stepsecurity-dmg/dmg-scan.sh`, which
drives `~/.local/share/stepsecurity-dmg/stepsecurity-dev-machine-guard`
and blocks on CRITICAL/HIGH findings. On a clean run it prints
`dev-machine-guard: clean` to stdout.

Unlike TruffleHog, this pass skips silently when the wrapper is absent or
not executable. A machine without DMG installed is never blocked by pass 6;
TruffleHog fails closed on a missing binary because that secret scan is a
required layer.

## Replacement standard, per context, and why

| Context | Form | Why |
|---|---|---|
| `*.sh`, shebang scripts | `$HOME` | Real env var, expands the same everywhere a shell runs it. |
| `*.md` | `~` | This repo already standardized on `~` for prose, with an explicit expansion note in `.claude/agents/zakia.md` telling readers to expand it manually. |
| `*.json`, everything else | `$HOME` | The existing `.claude/settings.json` already has both forms in the wild (`~/.claude/statusline.sh` in `statusLine.command`, and literal `$HOME/...` in a hook `command`), so both are proven to work once Claude Code hands the string to a shell. `$HOME` is picked as the default because it is a real env var in every context, not dependent on shell-specific tilde-expansion rules. |

Values that have no portable replacement (email, tailnet id, hostname)
are **blocked, not rewritten**. Rewriting a functional value like a
tailnet permission rule would silently break it (the rule stops
matching). The correct fix is to move that value out of the tracked
file entirely, into `scripts/commit-linter/identity.local` (see
"Identity config" above), which `.gitignore` already exempts via its
blanket `*.local` rule.

## Bypassing in an emergency

```
git commit --no-verify
```

Only do this if you have manually confirmed the diff has nothing
identifying or secret in it. The hook exists because that check is easy
to miss by eye.

## If the hook stops firing

`bd init` has hijacked `core.hooksPath` before. If commits stop being
linted, check:

```
git config core.hooksPath
```

If it points anywhere other than the default (unset, or `.git/hooks`),
that is why this hook is not running.

## Testing

Exercised against a throwaway git repo created outside this one, never
against a real commit here: `git init` a scratch dir, stage the case,
then run `python3 <repo>/scripts/commit-linter/lint_staged.py` from
inside it and check the exit code. (The old checked-in
`spikes/commit-linter/testbed/` went away with the `spikes/` ban.)

Covers: home path fix in `.sh` and `.md`, username-in-path and
username-before-`@` fixes before the bare-username block, bare username
block, secret regex block, tailnet block, partial staging block, a clean
commit, a TruffleHog-only finding (real-shaped fake Slack webhook) block,
a clean commit with the TruffleHog layer active, and a
missing-`trufflehog`-on-`PATH` block.
