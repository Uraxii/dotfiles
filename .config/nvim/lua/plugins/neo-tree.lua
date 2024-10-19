-- Neo-tree is a Neovim plugin to browse the file system
-- https://github.com/nvim-neo-tree/neo-tree.nvim
-- See examples @ https://neovimcraft.com/plugin/nvim-neo-tree/neo-tree.nvim/index.html

return {
  'nvim-neo-tree/neo-tree.nvim',
  version = '*',
  dependencies = {
    'nvim-lua/plenary.nvim',
    'nvim-tree/nvim-web-devicons', -- not strictly required, but recommended
    'MunifTanjim/nui.nvim',
  },
  cmd = 'Neotree',
  keys = {
    { '\\', ':Neotree reveal<CR>', desc = 'NeoTree reveal', silent = true },
  },
  opts = {
    close_if_last_window = true,
    filesystem = {
      window = {
        position = 'right',
        mappings = {
          ['\\'] = 'close_window',
        },
      },
      filtered_items = {
        never_show_by_pattern = {
          '*.meta',
          '*.cs.meta', -- meta files (mostly for Unity)
          '*.git', -- git files
        },
      },
    },
  },
}
