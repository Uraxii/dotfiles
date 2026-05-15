return {
  'folke/noice.nvim',
  event = 'VeryLazy',
  dependencies = {
    'MunifTanjim/nui.nvim',
    'rcarriga/nvim-notify',
  },
  -- Your original opts table is preserved
  opts = {
    cmdline = {
      view = 'cmdline',
      format = {
        cmdline = {
          title = '',
          icon = '󰞷 ',
          icon_hl_group = 'MyCmdlineIcon',
        },
        search_down = {
          icon = ' ',
        },
        search_up = {
          icon = ' ',
        },
        filter = {
          icon = ' ',
        },
        lua = {
          icon = ' ',
        },
        help = {
          icon = '󰋗 ',
        },
      },
    },
    messages = {
      view_search = false,
    },
    popupmenu = {
      enabled = true,
      backend = 'cmp',
    },
    presets = {
      bottom_search = true,
      command_palette = false,
      long_message_to_split = true,
      inc_rename = false,
    },
    routes = {
      {
        view = 'notify',
        filter = {
          event = 'msg_showmode',
          find = 'recording @',
        },
        opts = {
          skip = true,
        },
      },
    },
    -- We add this lsp table for consistent borders on hover docs
    lsp = {
      documentation = {
        border = {
          style = "rounded",
          highlight = "FloatBorder",
        },
      },
    },
    -- Cmdline popup window size (forced popup b/c cmdheight=0)
    views = {
      cmdline_popup = {
        position = { row = '50%', col = '50%' },
        size = { width = 80, height = 3 },
        border = { style = 'rounded' },
      },
    },
  },

  -- The new config function handles all transparency overrides
  config = function(_, opts)
    -- Standard setup call for noice
    require('noice').setup(opts)

    -- All transparency logic is now contained within this file
    local function set_transparency()
      local highlights = {
        -- General UI
        "Normal",
        "NormalFloat",
        "FloatBorder",
        -- Noice Specific UI
        "NoiceCmdline",
        "NoiceCmdlineIcon",
        "NoiceCmdlineIconCmdline",
        "NoiceCmdlineIconSearch",
        "NoiceCmdlineIconSearchDown",
        "NoiceCmdlineIconSearchUp",
        "NoiceCmdlineIconFilter",
        "NoiceCmdlineIconLua",
        "NoiceCmdlineIconHelp",
        "NoiceCmdlineIconInput",
        -- Cmdline floating popup (cmdheight=0 forces popup even w/
        -- view='cmdline'). Per-format suffix groups inherit theme bg.
        "NoiceCmdlinePopup",
        "NoiceCmdlinePopupBorder",
        "NoiceCmdlinePopupBorderCmdline",
        "NoiceCmdlinePopupBorderSearch",
        "NoiceCmdlinePopupBorderFilter",
        "NoiceCmdlinePopupBorderLua",
        "NoiceCmdlinePopupBorderHelp",
        "NoiceCmdlinePopupBorderInput",
        "NoiceCmdlinePopupTitle",
        "NoiceCmdlinePopupTitleCmdline",
        "NoiceCmdlinePopupTitleSearch",
        "NoiceCmdlinePopupTitleFilter",
        "NoiceCmdlinePopupTitleLua",
        "NoiceCmdlinePopupTitleHelp",
        "NoiceCmdlinePopupTitleInput",
      }

      for _, group in ipairs(highlights) do
        vim.api.nvim_set_hl(0, group, { bg = "none" })
      end
    end

    -- ColorScheme: re-apply on theme switch
    vim.api.nvim_create_autocmd("ColorScheme", {
      pattern = "*",
      callback = function()
        set_transparency()
      end,
    })

    -- CmdlineEnter: noice creates per-format icon hl groups lazily on
    -- first cmdline open. Re-apply each time so theme bg never sticks.
    vim.api.nvim_create_autocmd("CmdlineEnter", {
      pattern = "*",
      callback = function()
        vim.schedule(set_transparency)
      end,
    })

    -- Custom icon hl — own group, noice does not clobber.
    -- fg=NONE inherits Normal fg (theme-default text color, not blue).
    -- To pick a specific color: change fg to e.g. '#dca561' (kanagawa yellow).
    local function apply_icon_hl()
      vim.api.nvim_set_hl(0, 'MyCmdlineIcon', { fg = 'NONE', bg = 'NONE' })
    end
    apply_icon_hl()
    vim.api.nvim_create_autocmd({ 'ColorScheme', 'CmdlineEnter', 'VimEnter' }, {
      pattern = '*',
      callback = function() vim.schedule(apply_icon_hl) end,
    })

    -- Run once on startup as well
    set_transparency()
  end,
}
