# Keychron Q8 Pro — Moonlander-style layout (VIA / Keychron Launcher)

Source Moonlander layout: [`../moonlander/`](../moonlander/) (Oryx export, same repo)
Method: **VIA, no firmware compile.** Reversible. Tapping term fixed at ~200 ms (firmware default).

## Q8 Pro layer model (from Keychron QMK `wireless_playground`)
| Layer | Name | Reached by |
|-------|------|------------|
| 0 | Mac base | Mac/Win switch = Mac |
| 1 | **Win base** | Mac/Win switch = **Win** ← edit this on Linux |
| 2 | Mac Fn | — |
| 3 | Win Fn | hold **Fn** (BT/media/RGB — keep as-is) |
| 4 | **FN2** | hold the key right of Fn (between spacebars) ← symbol/num/nav |

Set the physical **Mac/Win switch to Win** before editing (Linux uses PC modifier positions).

## Step 1 — open the launcher
1. Chrome or Edge → https://launcher.keychron.com
2. Plug the Q8 Pro in by **USB-C** (config needs USB; wireless still works after).
3. Click **Authorize device** → pick the Keychron Q8 Pro.

## Step 2 — Layer 1 (Win base): home-row mods
Select **Layer 1**. Click each physical key, then type the keycode into the
**Special → Any** field (raw QMK keycodes are accepted). Tap = letter, hold = mod.

| Key | Assign (Any field) | Hold = |
|-----|--------------------|--------|
| A | *(leave KC_A)* | — |
| S | `LALT_T(KC_S)` | Alt |
| D | `LCTL_T(KC_D)` | Ctrl |
| F | `LSFT_T(KC_F)` | Shift |
| G | `LGUI_T(KC_G)` | Gui/Super |
| H | `RGUI_T(KC_H)` | Gui/Super |
| J | `LSFT_T(KC_J)` | Shift |
| K | `LCTL_T(KC_K)` | Ctrl |
| L | `LALT_T(KC_L)` | Alt |
| ; | *(leave KC_SCLN)* | — |

(If you also use the Mac side of the switch, repeat on Layer 0.)

## Step 3 — Layer 4 (FN2): symbols / numbers / nav
Select **Layer 4**. Keep the number row's F1–F12 default; set these (mirrors your
Moonlander MO(1) finger positions). Many duplicate keys the Q8 already has on base —
include only what you want.

| Phys key | Assign | | Phys key | Assign |
|----------|--------|-|----------|--------|
| Q | `KC_1` | | Y | `KC_6` |
| W | `KC_2` | | U | `KC_7` |
| E | `KC_3` | | I | `KC_8` |
| R | `KC_4` | | O | `KC_9` |
| T | `KC_5` | | P | `KC_0` |
| A | `KC_INS` | | J | `KC_MINS` (-) |
| S | `KC_RALT` | | K | `KC_EQL` (=) |
| D | `KC_LCTL` | | L | `KC_GRV` (\`) |
| F | `KC_LSFT` | | ; | `KC_QUOT` (') |
| G | `KC_LGUI` | | ' | `KC_BSLS` (\\) |
| X | `KC_PGUP` | | M | `KC_LBRC` ([) |
| C | `KC_PGDN` | | , | `KC_RBRC` (]) |
| V | `KC_HOME` | | | |
| B | `KC_END` | | | |

Left-home keys (A S D F G) become plain modifiers so you can hold a mod with the
left hand while the right hand types symbols — same as the Moonlander symbol layer.

## Notes
- Changes save to the keyboard automatically; no "flash" button needed in VIA.
- **Reset**: launcher → bottom-left menu → *Reset keyboard* (restores stock).
- Home-row mods feel laggier than your Moonlander's tuned 125 ms. If that bugs you,
  the only fix is compiling Keychron's QMK fork with `TAPPING_TERM 125` — ask and
  I'll set that path up.
