# commit-linter

A local git pre-commit hook for this dotfiles repo. Purpose: this repo is
public, so no machine- or user-identifying value, and no secret, should
ever land in a commit.

The hook is installed at `.git/hooks/pre-commit` (local, untracked, not
part of this repo's tracked files). It is a thin wrapper that calls the
real script here:

```
spikes/commit-linter/lint-staged.sh
```

Keeping the logic in a tracked file means it can be reviewed and improved
like normal code, while the hook installation itself stays local per
machine (as git hooks always are).

## What it catches

Only the STAGED content of staged files is scanned, i.e. exactly what
would be committed. Working-tree-only or untracked changes are never
touched.

1. **Expanded home paths.** `/var/home/nicole` and `/home/nicole` are
   auto-replaced with a portable form (see standard below).
2. **Bare username in path-like contexts.** `nicole` is replaced with
   `$USER` only when it sits next to a `/` or `@` (e.g.
   `/run/media/nicole/`, `nicole@host`). Plain prose mentions of the name,
   and the `nicolepaul.net` email domain, are left alone on purpose.
3. **Identity values with no portable form** are hard-blocked, not
   rewritten:
   - the email `accounts@nicolepaul.net`
   - the tailnet id `taild402ad` (covers `*.taild402ad.ts.net` hosts too)
   - the machine hostname, read live via `hostname` at hook run time
     (never hardcoded, so this still works if the machine is renamed)
4. **Secret-shaped strings.** Hard blocked, never auto-fixed: API key
   prefixes (`sk-ant-`, `sk-proj-`, `ghp_`, `github_pat_`, `gho_`,
   `xoxb-`, `xoxp-`, AWS `AKIA...`), private key headers, and any
   `*_KEY` / `*_TOKEN` / `*_SECRET` assignment to a long base64-ish
   value.
5. **Partial staging.** If a staged file also has unstaged changes on
   disk (the index and working tree disagree), the hook refuses to
   rewrite it silently. It blocks the commit and asks you to stage the
   whole file or none of it.
6. **Everything TruffleHog's 750+ detectors know about.** Runs after the
   five checks above, as a second, independent layer. Any finding blocks
   the commit; nothing is ever auto-fixed.

## Self-exemption for the linter's own files

`spikes/commit-linter/lint-staged.sh` and `spikes/commit-linter/README.md`
document the secret prefixes, the `_KEY`/`_TOKEN`/`_SECRET` pattern, the
email, and the tailnet id by name (as examples, and as the actual regex
source), so they legitimately contain the trigger text those checks look
for without containing a real leak. Left unexempted, the hook blocked
its own files on their first real commit, and would have silently
corrupted its own detection regex if the auto-fix pass had run on them
(it would have rewritten `/var/home/nicole` inside the sed patterns
themselves into `$HOME`, breaking detection).

So these two files only are exempt from the pattern-matching passes:
secret regex (pass 2), identity-value block (pass 3), and auto-fix
(pass 4). They are NOT exempt from TruffleHog (pass 5): a real secret
pasted into either file still blocks the commit, verified in testbed
test 12.

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
file entirely, into an untracked local file such as
`.claude/settings.local.json`, which `.gitignore` already exempts via
its `*.local` / `.claude/**/*local*` rules.

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

A throwaway test repo lives at `spikes/commit-linter/testbed/` (git
history for it is not meaningful; it exists only to exercise the hook).
Do not run this hook's tests against `/tmp`; that clears on reboot.

Covers: home path fix in `.sh` and `.md`, username-in-path fix vs email
domain left untouched, secret regex block, tailnet block, partial
staging block, a clean commit, a TruffleHog-only finding (real-shaped
fake Slack webhook) block, a clean commit with the TruffleHog layer
active, and a missing-`trufflehog`-on-`PATH` block.
