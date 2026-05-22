return {
  'rcarriga/nvim-notify',

  opts = {
    render = 'wrapped-compact',
    on_open = function(win)
      local buf = vim.api.nvim_win_get_buf(win)
      --vim.api.nvim_buf_set_option(buf, 'filetype', 'markdown')
    end,
  },
}
