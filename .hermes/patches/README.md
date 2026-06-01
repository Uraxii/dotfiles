# Hermes Nerd Font Icon Patches

After a Hermes update (`hermes update`), the source in `~/.hermes/hermes-agent/`
gets overwritten and the nerd font icon patch needs to be reapplied.

## What's here

| File | Purpose |
|------|---------|
| `display-nerd-font-icons.patch` | Git patch against `agent/display.py` — replaces hardcoded emojis in `get_cute_tool_message()` with `get_tool_emoji()` calls so the "completed" tool line respects skin `tool_emojis` |
| `reapply-after-update.sh` | One-shot reapply script. Run after `hermes update`. |

## Why this exists

The CLI TUI has **two rendering paths** for tool call icons:

1. **"preparing" line** — uses `get_tool_emoji()` → reads skin's `tool_emojis` ✓
2. **"completed" line** (`| 📖 read ...`) — `get_cute_tool_message()` had **hardcoded emojis** per tool ✗

The patch makes path 2 use `get_tool_emoji()` too, so tool icons come from the
skin consistently. Your skin (`synthwave-84.yaml`) defines nerd font glyphs in
`tool_emojis:` for all tools.

## Skin `tool_emojis` vs `display.tool_progress_overrides`

| System | Purpose | Reads from |
|--------|---------|------------|
| `get_tool_emoji()` | **CLI TUI** tool call headers | skin → tool registry → default |
| `tool_progress_overrides` | **Gateway** only (Telegram/Discord) | `display.tool_progress_overrides` in config.yaml |

The config's `display.tool_progress_overrides` is **never consulted** by the CLI.
Always put nerd font glyphs in the **skin's `tool_emojis`** for CLI display.

## To regenerate the patch after Hermes updates (if it diverges)

```bash
cd ~/.hermes/hermes-agent
# Make the same edit to agent/display.py
git diff agent/display.py > ~/dotfiles/.hermes/patches/display-nerd-font-icons.patch
```

## Codepoints in use

Tools use these nerd font codepoints (all present in 0xProto Nerd Font):

- U+F489 oct-terminal → terminal, process
- U+F15C fa-file_text → read_file, write_file, patch
- U+F002 fa-search → search_files, web_search, session_search
- U+F0AC fa-globe → web_extract, web
- U+F269 fa-firefox → browser_*
- U+F121 fa-code → execute_code, code_execution
- U+F06E fa-eye → vision_analyze, vision
- U+F1C5 fa-file_picture_o → image_generate, image_gen
- U+F1C0 fa-database → fact_store, fact_feedback
- U+F22F fa-dyalog → skills, skill_*, skills_list
- U+F0AE fa-tasks → todo
- U+F017 fa-clock_o → cronjob
- U+F059 fa-question_circle → clarify
- U+F0C0 fa-users → delegate_task, delegation
- U+F1D9 fa-send_o → send_message, messaging
- U+F028 fa-volume_up → text_to_speech
- U+F187 fa-box_archive → memory
