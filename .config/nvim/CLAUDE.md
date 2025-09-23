# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
This is a Neovim configuration based on kickstart.nvim, modularized into separate files for better organization. The configuration uses lazy.nvim for plugin management and follows a modular architecture.

## Commands

### Plugin Management
- `:Lazy` - Open lazy.nvim plugin manager UI
- `:Lazy sync` - Update all plugins
- `:Lazy restore` - Restore plugins to versions in lazy-lock.json
- `:Mason` - Open Mason LSP installer UI

### Configuration Testing
- `:checkhealth` - Run Neovim health checks
- `:luafile %` - Reload current Lua file (useful when editing config)
- `:source %` - Source current file

### Common Development Tasks
- Leader key is set to space (`<Space>`)
- `<leader>sf` - Search files with Telescope
- `<leader>sg` - Search with grep
- `<leader>sh` - Search help
- `-` - Open Oil file manager

## Architecture

### Module Loading Order
The configuration loads modules in this specific order (defined in init.lua):
1. `vim_settings` - Core Neovim settings (tab width, line numbers, etc.)
2. `keymaps` - All custom key mappings
3. `autocommands` - Automatic commands and hooks
4. `lazy_plugin_manager_setup` - Initializes lazy.nvim and loads all plugins
5. `fix_highlights` - Custom highlight group adjustments

### Plugin Configuration Pattern
Each plugin has its own file in `lua/plugins/` following this pattern:
```lua
return {
  'plugin/name',
  event = 'VeryLazy', -- or other lazy loading trigger
  config = function()
    -- plugin configuration
  end,
}
```

### Key Architectural Decisions
- **LSP-centric**: Heavy focus on Language Server Protocol with Mason for automatic installation
- **Modular plugins**: Each plugin gets its own configuration file rather than one monolithic file
- **Lazy loading**: Plugins load on specific events to improve startup time
- **Modern UI**: Uses Noice.nvim for floating command line and notifications

### Important Configuration Details
- Tab width is set to 4 spaces
- System clipboard integration is enabled
- Relative line numbers with absolute current line
- Kanagawa color theme is active (tokyonight available as alternative)
- Oil.nvim is the active file manager (Neo-tree and Yazi configurations exist but are commented out)

When modifying this configuration:
1. Follow the existing modular pattern - one file per plugin in `lua/plugins/`
2. Use lazy.nvim's event system for efficient loading
3. Test changes with `:source %` or restart Neovim
4. Update lazy-lock.json by running `:Lazy update` when adding new plugins