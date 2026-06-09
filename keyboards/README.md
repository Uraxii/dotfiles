# Keyboard layouts

Custom layouts for my mechanical keyboards. Reference material — **not** stowed
(excluded in `.stow-local-ignore`, never symlinked into `~/.config`).

Both boards share one philosophy: QWERTY alphas, **home-row mods**, and a hold
layer for numbers / symbols / nav.

## ZSA Moonlander — `moonlander/`

36ish-key layout built in Oryx, exported as QMK source.

- Oryx (edit online / re-flash): https://configure.zsa.io/moonlander/layouts/9qjQ3/NoXPJw/0
- `keymap.c`, `config.h`, `rules.mk`, `keymap.json` — editable QMK source.
- `firmware/*.bin` — pre-compiled firmware (reva + revb). Flash without Oryx:
  ```bash
  # check your board revision, then:
  wally-cli firmware/zsa_moonlander_revb_9qjQ3.bin   # or _reva_
  ```
- `ORYX-BUILD.md` — ZSA's notes on compiling from source.
- Tuning that matters: `TAPPING_TERM 125` (config.h) — the crisp home-row-mod feel.

## Keychron Q8 Pro (Alice) — `keychron-q8-pro/`

Same typing feel ported onto the 69-key Alice board via VIA (no firmware compile).

- `moonlander-style-via.md` — step-by-step Keychron Launcher guide: home-row mods
  on Layer 1, symbol/num/nav on Layer 4, with the exact keycode tables.
- Tradeoff: VIA can't set the 125 ms tapping term, so mods sit at the ~200 ms
  default. Compile Keychron's QMK fork if that ever needs fixing.
