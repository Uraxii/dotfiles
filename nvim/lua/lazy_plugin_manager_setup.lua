-- [[ Install `lazy.nvim` plugin manager ]]
--    See `:help lazy.nvim.txt` or https://github.com/folke/lazy.nvim for more info
local lazypath = vim.fn.stdpath 'data' .. '/lazy/lazy.nvim'
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  local lazyrepo = 'https://github.com/folke/lazy.nvim.git'
  local out = vim.fn.system { 'git', 'clone', '--filter=blob:none', '--branch=stable', lazyrepo, lazypath }
  if vim.v.shell_error ~= 0 then
    error('Error cloning lazy.nvim:\n' .. out)
  end
end ---@diagnostic disable-next-line: undefined-field
vim.opt.rtp:prepend(lazypath)

-- [[ Configure and install plugins ]]
--
--  To check the current status of your plugins, run
--    :Lazy
--
--  You can press `?` in this menu for help. Use `:q` to close the window
--
--  To update plugins you can run
--    :Lazy update
--
-- NOTE: Here is where you install your plugins.
-- Configurations for each plugin can be found in the respective <plugin>.lua file.

require('lazy').setup({
  -- [[ THEMES ]]
  -- require 'plugins.themes.tokyonight',
  require 'plugins.themes.kanagawa',

  -- [[ LANGUAGE SERVER SETUP ]]
  require 'plugins.lsp-config', -- Configures language servers
  require 'plugins.lazydev', -- Configures Lua language servers
  require 'plugins.conform', -- Text Autoformatter
  require 'plugins.nvim-cmp', -- Text completion engine
  require 'plugins.lint', -- Linter to check code for errors
  require 'plugins.debug', -- Enables debugging feature when runnning code

  -- [[ NAVIGATION ]]
  require 'plugins.telescope', -- Fuzzy file seachering
  require 'plugins.neo-tree', -- File tree browser

  -- [[ TEXT EDITING AND PARSING ]
  require 'plugins.vim-slueth', -- Detect tabstop and shiftwidth automatically
  require 'plugins.which-key', -- Proives key options popup
  require 'plugins.mini', -- Extends text-object capabilities; users can define custome text-objects
  require 'plugins.nvim-treesitter', -- Text parser (created syntax tree for files)
  require 'plugins.indent_line', -- Adds indention guides
  require 'plugins.autopairs', -- Creates closing characters when typing wrapped data (i.e. ", (, {, etc.)
  require 'plugins.gitsigns', -- Detect tabstop and shiftwidth automatically
}, {
  ui = {
    -- If you are using a Nerd Font: set icons to an empty table which will use the
    -- default lazy.nvim defined Nerd Font icons, otherwise define a unicode icons table
    icons = vim.g.have_nerd_font and {} or {
      cmd = '⌘',
      config = '🛠',
      event = '📅',
      ft = '📂',
      init = '⚙',
      keys = '🗝',
      plugin = '🔌',
      runtime = '💻',
      require = '🌙',
      source = '📄',
      start = '🚀',
      task = '📌',
      lazy = '💤 ',
    },
  },
})
