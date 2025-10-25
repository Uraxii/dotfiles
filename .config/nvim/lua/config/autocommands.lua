-- [[ Basic Autocommands ]]
--  See `:help lua-guide-autocommands`

-- Highlight when yanking (copying) text
--  Try it with `yap` in normal mode
--  See `:help vim.highlight.on_yank()`
vim.api.nvim_create_autocmd('TextYankPost', {
  desc = 'Highlight when yanking (copying) text',
  group = vim.api.nvim_create_augroup('kickstart-highlight-yank', { clear = true }),

  callback = function()
    vim.highlight.on_yank()
  end,
})

-- [[ NOTIFICATIONS ]]

-- Displays a message when saving a file
vim.api.nvim_create_autocmd('BufWritePost', {
  pattern = '*',
  callback = function(args)
    local filepath = vim.api.nvim_buf_get_name(args.buf)
    vim.notify('Saved: ' .. filepath, vim.log.levels.INFO, { title = 'Neovim' })
  end,
})

local delete_notify_id = nil
local delete_notify_timer = nil
local deleted_buffer = ''
local last_delete_time = nil

-- Displays a message showing when and what text gets deleted.
-- If the message is greater than
-- Try it with `dd` or `x` (assuming you have not changed the key bindings)
vim.api.nvim_create_autocmd('TextYankPost', {
  desc = 'Display a message when deleting text',
  group = vim.api.nvim_create_augroup('highlight-delete', { clear = true }),

  callback = function()
    local event = vim.v.event
    if event.operator == 'd' and event.regtype ~= '' then
      local deleted_text = vim.fn.getreg(event.regname)
      -- Only trim leading whitespace
      local trimmed = deleted_text:gsub('^%s*', '')

      local chunk = trimmed
      local ends_with_newline = false
      if deleted_text:sub(-1) == '\n' then
        ends_with_newline = true
      end

      local maxlen = 255
      if #chunk > maxlen then
        chunk = chunk:sub(1, maxlen) .. '…'
      end

      -- Time logic
      local now = vim.loop.hrtime() / 1e9
      if last_delete_time and (now - last_delete_time) > 0.5 then
        deleted_buffer = deleted_buffer .. '\n'
      end

      deleted_buffer = deleted_buffer .. chunk
      if ends_with_newline then
        deleted_buffer = deleted_buffer .. '\n'
      end

      last_delete_time = now

      vim.schedule(function()
        local ok, new_id = pcall(function()
          return vim.notify(string.format('deleted:[%s]', deleted_buffer), vim.log.levels.INFO, {
            title = 'Deleted Text',
            render = 'wrapped-compact',
            replace = delete_notify_id,
            timeout = false,
          })
        end)
        if ok and new_id then
          delete_notify_id = new_id
        end

        -- Reset the timer
        if delete_notify_timer then
          delete_notify_timer:stop()
          delete_notify_timer:close()
        end
        delete_notify_timer = vim.loop.new_timer()
        delete_notify_timer:start(
          5000,
          0,
          vim.schedule_wrap(function()
            -- Robust close logic for nvim-notify wrapped-compact
            if delete_notify_id then
              local notify = package.loaded['notify'] and require 'notify' or nil
              if notify and notify.dismiss then
                notify.dismiss { id = delete_notify_id }
              else
                vim.notify(' ', vim.log.levels.INFO, { replace = delete_notify_id, timeout = 100 })
              end
              delete_notify_id = nil
            end
            if delete_notify_timer then
              delete_notify_timer:stop()
              delete_notify_timer:close()
              delete_notify_timer = nil
            end
            deleted_buffer = ''
            last_delete_time = nil
          end)
        )
      end)
    end
  end,
})

-- Used to track which message is displaying the current macro recording.
local macro_notify_id = nil
-- Timer used to capture keystrokes when recoding macros
local macro_record_timer = nil

-- Displays message when macro recording begins.
-- This is intended to be used with the Noice plugin, which does not show this message by default.
-- Try it with `qa`

local function on_macro_key(char)
  local reg = vim.fn.reg_recording()
  if reg ~= '' then
    -- Append the key to our buffer (you can filter unwanted keys if you want)
    macro_keys = macro_keys .. char
    -- Truncate for display
    local maxlen = 80
    local display_macro = macro_keys
    if #display_macro > maxlen then
      display_macro = display_macro:sub(1, maxlen) .. '…'
    end
    -- Update notification
    local ok, new_id = pcall(function()
      return vim.notify(display_macro, vim.log.levels.INFO, {
        title = 'Macro Recording (Live)',
        replace = macro_notify_id,
        timeout = false,
        render = 'wrapped-compact',
      })
    end)
    if ok and new_id then
      macro_notify_id = new_id
    end
    if not ok then
      macro_notify_id = nil
    end
  end
end

vim.api.nvim_create_autocmd('RecordingEnter', {
  callback = function()
    local reg = vim.fn.reg_recording()
    if reg ~= '' then
      macro_keys = ''
      macro_notify_id = vim.notify('Recording macro: (waiting for first key...)', vim.log.levels.INFO, {
        title = 'Recording Keystrokes',
        timeout = false,
        render = 'wrapped-compact',
      })
      -- Start capturing keys
      vim.on_key(on_macro_key, macro_on_key_ns)
    end
  end,
})

-- Displays message when macro recording ends.
-- Shows which register the macro was recorded to (i.e. @a) and the content of the macro.
-- Try it with `qaq`
vim.api.nvim_create_autocmd('RecordingLeave', {
  callback = function()
    local reg = vim.v.event and vim.v.event.regname or ''
    if macro_record_timer then
      macro_record_timer:stop()
      macro_record_timer:close()
      macro_record_timer = nil
    end
    if reg ~= '' and macro_notify_id then
      vim.schedule(function()
        local macro = vim.fn.getreg(reg)
        local display_macro = macro
        local maxlen = 80
        if #display_macro > maxlen then
          display_macro = display_macro:sub(1, maxlen) .. '…'
        end
        local ok, _ = pcall(function()
          vim.notify(string.format('Recorded macro in @%s:\n%s', reg, display_macro), vim.log.levels.INFO, {
            title = 'Macro Recording Finished',
            replace = macro_notify_id,
            timeout = 3000,
            render = 'wrapped-compact',
          })
        end)
        macro_notify_id = nil
      end)
    end
  end,
})

-- This function makes a list of highlight groups transparent
local function set_transparency()
  local highlights = {
    'Normal',
    'NormalNC',
    'NormalFloat',
    'FloatBorder',
    'SignColumn',
    'LineNr',
    'CursorLineNr',
    'EndOfBuffer',
    'MsgArea',
    'Pmenu',
    'PmenuSel',
    'PmenuSbar',
    'PmenuThumb',
  }

  for _, group in ipairs(highlights) do
    vim.api.nvim_set_hl(0, group, { bg = 'none' })
  end
end

-- Apply transparency AFTER a colorscheme is loaded
vim.api.nvim_create_autocmd('ColorScheme', {
  pattern = '*',
  callback = function()
    set_transparency()
  end,
})

-- Initial call for when the config is first loaded
set_transparency()
