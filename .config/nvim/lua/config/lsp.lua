-- LSP config files can be found on the nvim-lspconfig repository.
-- https://github.com/neovim/nvim-lspconfig/tree/master/lsp

-- Lua files located in root/lsp
vim.lsp.enable {
  'gdscript',
  'lua_ls',
}

vim.diagnostic.config {
  virtual_lines = true,
  virtual_text = true,
  underline = true,
  update_in_insert = false,
  severity_sort = true,
  float = {
    border = 'rounded',
    source = true,
  },
  signs = {
    text = {
      [vim.diagnostic.severity.ERROR] = '󰅚 ',
      [vim.diagnostic.severity.WARN] = '󰀪 ',
      [vim.diagnostic.severity.INFO] = '󰋽 ',
      [vim.diagnostic.severity.HINT] = '󰌶 ',
    },
    numhl = {
      [vim.diagnostic.severity.ERROR] = 'ErrorMsg',
      [vim.diagnostic.severity.WARN] = 'WarningMsg',
    },
  },
}

-- This checks if we are in a Godot project.
-- If we are, then listen to the godothost file.
-- This allows the Godot editor to do things like open files in nvim without needing to create a new instance of nvim.

-- Ensure the Godot editor options are set:
-- Use External Editor: On
-- Normal setup:
--  Exec Path: nvim
--  Exec Flags: --server ./godothost.pipe --remote-send "<C-\><C-N>:drop {file}<CR>{line}G{col}|"
-- If godot is sandboxed (i.e. running as a flatpak)
--  Exec Path: /usr/bin/flatpak-spawn
--  Exec Flags: --host /usr/bin/nvim --server ./godothost.pipe --remote-send "<C-\><C-N>:drop {file}<CR>{line}G{col}|"

local gdproject = io.open(vim.fn.getcwd() .. '/project.godot', 'r')
if gdproject then
  io.close(gdproject)
  vim.fn.serverstart './godothost.pipe'
  vim.notify 'Starting Godot server.'
end
