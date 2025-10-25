-- lua/lsp/pyright.lua
--
local capabilities = require('cmp_nvim_lsp').default_capabilities()

vim.lsp.config('pyright', {
  cmd = { 'pyright-langserver', '--stdio' },
  filetypes = { 'python' },
  root_markers = { 'pyproject.toml', '.git' },
  capabilities = capabilities,
})

vim.lsp.enable('pyright')
