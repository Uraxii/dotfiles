---
name: proton-pass-cli
description: Retrieve credentials (API keys, passwords, tokens, SSH keys) from Proton Pass via the pass-cli tool, using a Personal Access Token held in the OS keyring. Use whenever a task needs a secret that lives in Proton Pass - e.g. "get the OpenAI key", "read the litellm master key", "fetch the DB password", "log in to <service> using my stored credentials", or before running any tool/gateway that reads secrets from the MachineSecrets vault. Covers session bootstrap, authenticated reads with a mandatory access reason, and auto-recovery from an expired session.
---

# Proton Pass CLI

Read secrets from Proton Pass on the command line with `pass-cli`. Authentication is a **Personal Access Token (PAT)** stored in the OS keyring (secret-service / KWallet) - never in a file, never in this repo.

## The token lives in the keyring, not here

There is no token in this skill. Retrieve it at runtime:

```bash
PROTON_PASS_PERSONAL_ACCESS_TOKEN="$(secret-tool lookup service proton-pass-cli account machinesecrets-pat)"
```

If that lookup returns empty, the PAT has not been stored on this machine yet. Store it (paste the current PAT on stdin):

```bash
printf '%s' 'PASTE_PAT_HERE' | secret-tool store --label="Proton Pass CLI PAT (MachineSecrets)" service proton-pass-cli account machinesecrets-pat
```

Rotating the PAT = re-run that `store` command with the new value. Nothing else changes.

## Prerequisites

- `pass-cli` installed: `pass-cli --version` (if missing, see <https://protonpass.github.io/pass-cli/get-started/installation/>).
- `secret-tool` (libsecret) with an active secret-service provider (KDE `ksecretd` / `kwalletd`, or gnome-keyring).

## 1. Ensure an authenticated session

Always check before doing real work - the session can expire mid-task:

```bash
export PROTON_PASS_SESSION_DIR="/tmp/pass-agent-$USER"   # isolate from other sessions
pass-cli info    # exit 0 + session details = good; non-zero = must log in
```

If not authenticated, log in with the PAT from the keyring:

```bash
export PROTON_PASS_SESSION_DIR="/tmp/pass-agent-$USER"
pass-cli logout --force 2>/dev/null || true                       # clear any stale session
PROTON_PASS_PERSONAL_ACCESS_TOKEN="$(secret-tool lookup service proton-pass-cli account machinesecrets-pat)" pass-cli login
pass-cli info    # verify
```

`PROTON_PASS_SESSION_DIR` must be set to the **same** value for every subsequent `pass-cli` command in the task, or they will not see the session.

## 2. Verify access

```bash
pass-cli vault list      # expect the MachineSecrets vault
pass-cli share list      # vaults + directly-shared items granted to this PAT
```

The current PAT is scoped to the **MachineSecrets** vault (Owner).

## 3. Read an item (reason is mandatory)

`item view`, `item create*`, `item update`, `item trash`, `item untrash`, and `vault update` all REQUIRE `PROTON_PASS_AGENT_REASON` describing why you need access.

```bash
# whole item
PROTON_PASS_AGENT_REASON="why you need this" pass-cli item view \
  --vault-name "MachineSecrets" --item-title "openai"

# a single field only (preferred - least exposure)
PROTON_PASS_AGENT_REASON="start litellm gateway" pass-cli item view \
  --vault-name "MachineSecrets" --item-title "openai" --field api-key

# by pass:// URI
PROTON_PASS_AGENT_REASON="..." pass-cli item view "pass://SHARE_ID/ITEM_ID"
```

## Discovering vaults and items

```bash
pass-cli vault list --output json
pass-cli item list --vault-name "MachineSecrets" --output json
pass-cli item list --output json          # all accessible items
```

Use `--output json` when parsing programmatically.

## Auto-recovery from a dead session

If any command fails with an authentication error or non-zero exit:

1. `pass-cli logout --force`
2. Re-run the login block in step 1
3. `pass-cli info` to confirm
4. Retry the original command

## Health checks

```bash
pass-cli info    # account type + session details
pass-cli test    # connectivity to the Proton Pass API
pass-cli agent instructions   # upstream usage reference
```

## Rules

- Never write the PAT or any retrieved secret to a file, a tracked path, or a log. Read into a shell variable, use it, let it fall out of scope.
- Prefer `--field` over whole-item reads.
- Always give a truthful, specific `PROTON_PASS_AGENT_REASON` (it is audited).

Full docs: <https://protonpass.github.io/pass-cli/>
