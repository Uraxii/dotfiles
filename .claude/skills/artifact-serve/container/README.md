# artifact-serve container

Rootless-podman packaging of `artifact-serve.py` for durable, boot-surviving
deployment via a systemd user quadlet.

## Files

- `Containerfile` — builds the image (`python:3.13-slim`, stdlib-only, no
  `pip install`).
- `artifact-serve.container` — the quadlet unit. Tracked copy; the install
  target is `~/.config/containers/systemd/artifact-serve.container` (see
  Install below).

## Build

```bash
cd ~/dotfiles/.claude/skills/artifact-serve
podman build -t localhost/artifact-serve:latest -f container/Containerfile .
```

## Install the quadlet

```bash
mkdir -p ~/.config/containers/systemd
cp ~/dotfiles/.claude/skills/artifact-serve/container/artifact-serve.container \
   ~/.config/containers/systemd/artifact-serve.container
systemctl --user daemon-reload
systemctl --user start artifact-serve
```

The unit carries `WantedBy=default.target`, so quadlet auto-wires it into
`default.target.wants` on every `daemon-reload`/boot — no separate
`systemctl enable` needed. It also needs `loginctl enable-linger $USER` (a
one-time, already-done step on this host) so the user's systemd instance
keeps running, and the container with it, without an active login session.

Re-run the `cp` + `daemon-reload` after any edit to the tracked quadlet file;
the `~/.config/containers/systemd/` copy is the live one, not a symlink to
the repo.

## Mounts and their security note

artifact-serve stages every artifact into `/tmp/claude-artifacts/<project>/`
as a **symlink** pointing at the real file elsewhere on disk (see
`artifact-serve.py push`). The tracked quadlet mounts only the paths the
renamed entrypoint itself needs:

| Mount | Path | Mode | Why |
|---|---|---|---|
| staging root | `/tmp/claude-artifacts` | rw | where artifacts get symlinked in; also the pid/port/log bookkeeping files |
| feedback store | `~/.local/share/claude-artifacts` | rw | durable sqlite feedback DB + uploaded review files |

**Security implication**: the broad home-directory mount is gone. The current
quadlet only exposes the staging root plus the durable feedback store to the
container, which keeps the host read surface much smaller than the old shape.
If you need container mode to follow symlink targets outside those mounted
paths, add explicit extra binds for those roots instead of reintroducing a
whole-home mount.

The container also runs `--userns keep-id --user <uid>:<uid>` so files it
writes into the two `rw` mounts come out owned by the real host user, not
container root or a shifted subuid range. SELinux (enforcing on this host)
still needs the label check disabled for the feedback-dir bind, so the
quadlet keeps `SecurityLabelDisable=true` as the trade-off that goes with this
narrow allowlist.

## Networking

The current quadlet does not use `Network=host`. It sets
`ARTIFACT_SERVE_HOST=0.0.0.0` inside the container and publishes only
`127.0.0.1:9099:9099` on the host with `PublishPort=`. Result: the app is
reachable on host loopback at `http://127.0.0.1:9099/`, while keeping normal
Podman network-namespace isolation.

Tailscale stays entirely a **host** concern — it is never run inside the
container. To publish the container over the tailnet, run on the host:

```bash
tailscale serve --bg --https=443 http://127.0.0.1:9099
```

The app's own `expose`/`unexpose` verbs still work for this (they just shell
out to the `tailscale` CLI), but only when run directly on the host, not
inside the container image (no tailscale binary is installed there).

## Foreground mode (`run` verb)

artifact-serve's normal `start` verb forks + writes a pidfile (a CLI daemon
model). Containers and systemd want a single foreground process they
supervise directly, so a new `run` verb was added: same server, no fork, no
`setsid`, no pidfile — it blocks in the foreground until SIGTERM/SIGINT,
logging to stdout (captured by `podman logs` / `journalctl --user`). This is
the only code change made to `artifact-serve.py` for containerization.

## Bare-to-container cutover

1. Build the image and install the quadlet (above).
2. Stop the bare instance with its own `stop` verb:
   ```bash
   ~/dotfiles/.claude/skills/artifact-serve/scripts/artifact-serve.py stop
   ```
   Note: `stop` also runs `tailscale serve --https=443 off` as part of its
   normal shutdown — re-run the `tailscale serve --bg ...` command above
   once the container is up, to point port 443 back at 9099.
3. `systemctl --user start artifact-serve` (or let the already-running unit
   take over the now-free port).
4. Verify: `curl http://127.0.0.1:9099/`, an artifact URL, and that
   `systemctl --user restart artifact-serve` survives cleanly.
