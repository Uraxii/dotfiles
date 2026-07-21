# Spike: beads + beads-ui browser write path

Question: can a human answer and close a board ticket from the browser UI?
Answer: yes. beads-ui is read-write. Verified by driving its own websocket
backend directly, then confirming the changes through the bd CLI.

## What is installed

- bd (beads) v1.1.0 at `~/.local/bin/bd` (plus a `beads` symlink).
  Installed by the official install script (`install-bd.sh` in this dir).
  Uninstall: `rm ~/.local/bin/bd ~/.local/bin/beads`
- beads-ui, local npm install in `./node_modules` (not global).
  Uninstall: delete this directory.

## The test scenario

- `beads-board-orq` (decision, P1): "Which art style: pixel or painted?"
- `beads-board-yja` (task, P1): "Generate hero sprite candidates",
  blocked by the question above.

While the question is open, `bd ready` hides the work ticket and
`bd blocked` shows it. Closing the question makes the work ticket ready.
The scenario is left live (question open) so you can close it yourself in
the browser.

## Start / stop the UI

```sh
cd ~/dotfiles/spikes/beads-board
PATH=/home/linuxbrew/.linuxbrew/bin:$PATH ./node_modules/.bin/bdui start
./node_modules/.bin/bdui stop
```

It serves on http://localhost:3000 and runs as a background daemon.
The Board view has Blocked / Ready / In progress / Closed columns and
inline editing. Comment on the question ticket to answer it, then set its
status to closed and watch the work ticket move to Ready.

## Findings

- beads-ui writes over a websocket at `/ws`. Message types include
  `update-status`, `update-assignee`, `update-priority`, `edit-text`,
  `create-issue`, `add-comment`. Each one shells out to the bd CLI on the
  server side, so browser edits are real board edits.
- `ws-write-test.mjs` in this dir exercises that path headlessly:
  it added a comment and closed the question ticket, both confirmed via
  `bd show` and `bd comments`.
- Claims are atomic: two concurrent `bd update <id> --claim` calls from
  different actors resulted in exactly one winner; the loser got
  "Error claiming ... issue already claimed by ...".
- bd 1.1.0 issue types: bug, feature, task, epic, chore, decision.
  No dedicated question or message type exposed by `bd create -t`;
  decision is the natural fit for a question ticket.

## Caveats from install

- `bd init` auto-committed its `.beads/` files to the dotfiles repo
  (commit c5f2884, local only, not pushed).
- `bd init` also set `core.hooksPath` in the dotfiles repo to
  `~/dotfiles/.beads/hooks`, which does not exist (it
  assumed it was running at the repo root). This disables git hooks for
  the whole dotfiles repo. Fix:
  `git -C ~/dotfiles config --unset core.hooksPath`
