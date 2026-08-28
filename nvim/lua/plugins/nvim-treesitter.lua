return { -- Highlight, edit, and navigate code
  'nvim-treesitter/nvim-treesitter',
  branch = 'main',
  lazy = false,
  build = ':TSUpdate',
  -- [[ Configure Treesitter ]] See `:help nvim-treesitter`
  config = function()
    local ts = require 'nvim-treesitter'
    local wanted = {
      'bash',
      'c',
      'diff',
      'gdscript',
      'godot_resource',
      'gdshader',
      'html',
      'lua',
      'luadoc',
      'markdown',
      'markdown_inline',
      'query',
      'vim',
      'vimdoc',
    }
    -- Install only parsers Neovim cannot already load (bundled or on rtp);
    -- install() otherwise re-downloads every start until they are rebuilt.
    ts.install(vim.tbl_filter(function(lang)
      return not vim.treesitter.language.add(lang)
    end, wanted))

    -- Ruby keeps vim's indent rules and regex highlighting on top of treesitter.
    local vim_regex_highlight = { ruby = true }

    vim.api.nvim_create_autocmd('FileType', {
      group = vim.api.nvim_create_augroup('treesitter-start', { clear = true }),
      callback = function(args)
        local ft = args.match
        local lang = vim.treesitter.language.get_lang(ft)
        if not lang or not vim.treesitter.language.add(lang) then
          return
        end
        vim.treesitter.start(args.buf, lang)
        if vim_regex_highlight[ft] then
          vim.bo[args.buf].syntax = 'ON'
        elseif vim.treesitter.query.get(lang, 'indents') then
          vim.bo[args.buf].indentexpr = "v:lua.require'nvim-treesitter'.indentexpr()"
        end
      end,
    })
  end,
  -- There are additional nvim-treesitter modules that you can use to interact
  -- with nvim-treesitter. You should go explore a few and see what interests you:
  --
  --    - Show your current context: https://github.com/nvim-treesitter/nvim-treesitter-context
  --    - Treesitter + textobjects: https://github.com/nvim-treesitter/nvim-treesitter-textobjects
}
