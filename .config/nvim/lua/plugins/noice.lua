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
      format = {
        cmdline = {
          title = 'Command',
          icon = '>_',
        },
      },
    },
    presets = {
      bottom_search = false,
      command_palette = true,
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
    -- We add this views table to control the border style
    views = {
      cmdline_popup = {
        border = {
          style = "rounded",
          highlight = "FloatBorder",
        },
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
        "NoiceCmdlinePopup",
        "NoiceCmdlinePopupBorder",
        "NoiceCmdlineIcon",
        "NoiceCmdlineTitle",
      }

      for _, group in ipairs(highlights) do
        vim.api.nvim_set_hl(0, group, { bg = "none" })
      end
    end

    -- We set up an autocommand that runs AFTER a colorscheme is loaded.
    -- This ensures our transparency settings override the theme's colors.
    vim.api.nvim_create_autocmd("ColorScheme", {
      pattern = "*",
      callback = function()
        set_transparency()
      end,
    })

    -- Run once on startup as well
    set_transparency()
  end,
}
