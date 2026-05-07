-- Generated wire-protocol formatters for the dmp168.
--
-- DO NOT EDIT. Regenerate with: python -m spec.codegen.emit_lua
-- Source: spec/protocol.yaml
-- Spec hash: 69d3d20d2ec63493
-- Device: Blustream dmp168
-- Firmware baseline: 1.5.0

local M = {}

M.DEFAULT_PORT = 8000
M.ALTERNATIVE_PORT = 23
M.TERMINATOR = "\r\n"

function M.format_status(_)
    -- Get system status and port status.
    return "STATUS"
end

function M.format_uptime(_)
    -- Get system uptime.
    return "UPTIME"
end

function M.format_temp(_)
    -- Get system temperature.
    return "TEMP"
end

function M.format_power_on(_)
    -- Power on, system run on normal state.
    return "PON"
end

function M.format_power_off(_)
    -- Power off, system run on power save state.
    return "POFF"
end

function M.format_standby(args)
    -- Set device standby mode (0=Sleep, 1=Standby).
    args = args or {}
    local mode = args.mode
    if not (mode == 0 or mode == 1) then
        error("Invalid standby mode '" .. tostring(mode) .. "'. Valid options are: 0 (Sleep) or 1 (Standby). Please choose a valid mode.")
    end
    local cmd = ""
    cmd = cmd .. "STANDBY "
    cmd = cmd .. tostring(mode)
    return cmd
end

function M.format_disable_auto_standby(_)
    -- Disable the auto-standby timer (persists across reboots).
    return "AUTO STB 0"
end

function M.format_reboot(_)
    -- Reboot system.
    return "REBOOT"
end

function M.format_output_volume(args)
    -- Set output volume.
    args = args or {}
    local output = args.output
    local level = args.level
    local unit = args.unit
    if unit == nil then unit = "percent" end
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if output < 0 or output > 8 then
        error("Invalid output channel '" .. tostring(output) .. "'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    if not (unit == "percent" or unit == "dB") then
        error("Invalid unit '" .. tostring(unit) .. "'. Valid options are: 'percent' or 'dB'. Please choose a valid unit.")
    end
    local cmd = ""
    cmd = cmd .. "OUT "
    cmd = cmd .. tostring(output)
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    cmd = cmd .. " VOL"
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    cmd = cmd .. " "
    cmd = cmd .. tostring(level)
    if unit == "dB" and not (level == "+" or level == "-") then
        cmd = cmd .. " dB"
    end
    return cmd
end

function M.format_output_mute(args)
    -- Set output mute on or off.
    args = args or {}
    local output = args.output
    local mute = args.mute
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if output < 0 or output > 8 then
        error("Invalid output channel '" .. tostring(output) .. "'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "OUT "
    cmd = cmd .. tostring(output)
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    cmd = cmd .. " MUTE"
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    if mute then
        cmd = cmd .. " ON"
    end
    if not mute then
        cmd = cmd .. " OFF"
    end
    return cmd
end

function M.format_output_channel_lock(args)
    -- Set output channel lock on or off.
    args = args or {}
    local output = args.output
    local lock = args.lock
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if output < 0 or output > 8 then
        error("Invalid output channel '" .. tostring(output) .. "'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "OUT "
    cmd = cmd .. tostring(output)
    cmd = cmd .. " CH LOCK"
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    if lock then
        cmd = cmd .. " ON"
    end
    if not lock then
        cmd = cmd .. " OFF"
    end
    return cmd
end

function M.format_output_delay(args)
    -- Set output delay time.
    args = args or {}
    local output = args.output
    local delay_ms = args.delay_ms
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if output < 0 or output > 8 then
        error("Invalid output channel '" .. tostring(output) .. "'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    end
    if delay_ms < 0 or delay_ms > 500 then
        error("Invalid delay value '" .. tostring(delay_ms) .. "'. Delay must be between 0-500 milliseconds. Please choose a valid delay.")
    end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "OUT "
    cmd = cmd .. tostring(output)
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    cmd = cmd .. " DELAY "
    cmd = cmd .. tostring(delay_ms)
    return cmd
end

function M.format_output_mix(args)
    -- Set output mixing mode.
    args = args or {}
    local output = args.output
    local mode = args.mode
    if output < 0 or output > 8 then
        error("Invalid output channel '" .. tostring(output) .. "'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    end
    if mode < 0 or mode > 6 then
        error("Invalid mix mode '" .. tostring(mode) .. "'. Mix mode must be between 0-6. Please choose a valid mode.")
    end
    local cmd = ""
    cmd = cmd .. "OUT "
    cmd = cmd .. tostring(output)
    cmd = cmd .. " MIX "
    cmd = cmd .. tostring(mode)
    return cmd
end

function M.format_output_master_volume(args)
    -- Set output master volume.
    args = args or {}
    local level = args.level
    local unit = args.unit
    if unit == nil then unit = "percent" end
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    if not (unit == "percent" or unit == "dB") then
        error("Invalid unit '" .. tostring(unit) .. "'. Valid options are: 'percent' or 'dB'. Please choose a valid unit.")
    end
    local cmd = ""
    cmd = cmd .. "OUT MASTER VOL"
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    cmd = cmd .. " "
    cmd = cmd .. tostring(level)
    if unit == "dB" and not (level == "+" or level == "-") then
        cmd = cmd .. " dB"
    end
    return cmd
end

function M.format_output_master_mute(args)
    -- Set output master mute on or off.
    args = args or {}
    local mute = args.mute
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "OUT MASTER MUTE"
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    if mute then
        cmd = cmd .. " ON"
    end
    if not mute then
        cmd = cmd .. " OFF"
    end
    return cmd
end

function M.format_route(args)
    -- Route input to output.
    args = args or {}
    local output = args.output
    local input_ch = args.input_ch
    local output_channel = args.output_channel
    if output_channel == nil then output_channel = "LR" end
    local input_channel = args.input_channel
    if input_channel == nil then input_channel = "LR" end
    if output < 0 or output > 8 then
        error("Invalid output channel '" .. tostring(output) .. "'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    end
    if input_ch < 1 or input_ch > 24 then
        error("Invalid input channel '" .. tostring(input_ch) .. "'. Input must be between 1-24. Please choose a valid input.")
    end
    if not (output_channel == "L" or output_channel == "R" or output_channel == "LR") then
        error("Invalid output channel '" .. tostring(output_channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    if not (input_channel == "L" or input_channel == "R" or input_channel == "LR") then
        error("Invalid input channel '" .. tostring(input_channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "OUT "
    cmd = cmd .. tostring(output)
    if output_channel ~= "LR" then
        cmd = cmd .. " " .. tostring(output_channel)
    end
    cmd = cmd .. " FR "
    cmd = cmd .. tostring(input_ch)
    if input_channel ~= "LR" then
        cmd = cmd .. " " .. tostring(input_channel)
    end
    return cmd
end

function M.format_output_remove(args)
    -- Remove input from output.
    args = args or {}
    local output = args.output
    local input_ch = args.input_ch
    local output_channel = args.output_channel
    if output_channel == nil then output_channel = "LR" end
    local input_channel = args.input_channel
    if input_channel == nil then input_channel = "LR" end
    if output < 0 or output > 8 then
        error("Invalid output channel '" .. tostring(output) .. "'. Output must be between 0-8 (0=All outputs). Please choose a valid output.")
    end
    if input_ch < 1 or input_ch > 24 then
        error("Invalid input channel '" .. tostring(input_ch) .. "'. Input must be between 1-24. Please choose a valid input.")
    end
    if not (output_channel == "L" or output_channel == "R" or output_channel == "LR") then
        error("Invalid output channel '" .. tostring(output_channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    if not (input_channel == "L" or input_channel == "R" or input_channel == "LR") then
        error("Invalid input channel '" .. tostring(input_channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "OUT "
    cmd = cmd .. tostring(output)
    if output_channel ~= "LR" then
        cmd = cmd .. " " .. tostring(output_channel)
    end
    cmd = cmd .. " REM "
    cmd = cmd .. tostring(input_ch)
    if input_channel ~= "LR" then
        cmd = cmd .. " " .. tostring(input_channel)
    end
    return cmd
end

function M.format_input_gain(args)
    -- Set input gain.
    args = args or {}
    local input_ch = args.input_ch
    local gain = args.gain
    local channel = args.channel
    if channel == nil then channel = "LR" end
    local unit = args.unit
    if input_ch < 0 or input_ch > 16 then
        error("Invalid input channel '" .. tostring(input_ch) .. "'. Input must be between 0-16 (0=All inputs). Please choose a valid input.")
    end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "IN "
    cmd = cmd .. tostring(input_ch)
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    cmd = cmd .. " GAIN"
    cmd = cmd .. " "
    cmd = cmd .. tostring(gain)
    if unit == "dB" and not (gain == "+" or gain == "-") then
        cmd = cmd .. " dB"
    end
    return cmd
end

function M.format_input_mute(args)
    -- Set input mute on or off.
    args = args or {}
    local input_ch = args.input_ch
    local mute = args.mute
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if input_ch < 0 or input_ch > 16 then
        error("Invalid input channel '" .. tostring(input_ch) .. "'. Input must be between 0-16 (0=All inputs). Please choose a valid input.")
    end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "IN "
    cmd = cmd .. tostring(input_ch)
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    cmd = cmd .. " MUTE"
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    if mute then
        cmd = cmd .. " ON"
    end
    if not mute then
        cmd = cmd .. " OFF"
    end
    return cmd
end

function M.format_preset_save(args)
    -- Save current config to preset.
    args = args or {}
    local preset = args.preset
    if preset < 1 or preset > 8 then
        error("Invalid preset number '" .. tostring(preset) .. "'. Preset must be between 1-8. Please choose a valid preset.")
    end
    local cmd = ""
    cmd = cmd .. "PRESET "
    cmd = cmd .. tostring(preset)
    cmd = cmd .. " SAVE"
    return cmd
end

function M.format_preset_recall(args)
    -- Recall preset config to current setting.
    args = args or {}
    local preset = args.preset
    if preset < 1 or preset > 8 then
        error("Invalid preset number '" .. tostring(preset) .. "'. Preset must be between 1-8. Please choose a valid preset.")
    end
    local cmd = ""
    cmd = cmd .. "PRESET "
    cmd = cmd .. tostring(preset)
    cmd = cmd .. " APPLY"
    return cmd
end

function M.format_preset_delete(args)
    -- Delete preset from system.
    args = args or {}
    local preset = args.preset
    if preset < 1 or preset > 8 then
        error("Invalid preset number '" .. tostring(preset) .. "'. Preset must be between 1-8. Please choose a valid preset.")
    end
    local cmd = ""
    cmd = cmd .. "PRESET "
    cmd = cmd .. tostring(preset)
    cmd = cmd .. " DELETE"
    return cmd
end

function M.format_preset_status(args)
    -- Get preset configuration status.
    args = args or {}
    local preset = args.preset
    if preset < 1 or preset > 8 then
        error("Invalid preset number '" .. tostring(preset) .. "'. Preset must be between 1-8. Please choose a valid preset.")
    end
    local cmd = ""
    cmd = cmd .. "PRESET "
    cmd = cmd .. tostring(preset)
    cmd = cmd .. " STATUS"
    return cmd
end

function M.format_group_volume(args)
    -- Set group volume.
    args = args or {}
    local group = args.group
    local level = args.level
    local unit = args.unit
    if unit == nil then unit = "percent" end
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if group < 0 or group > 4 then
        error("Invalid group number '" .. tostring(group) .. "'. Group must be between 0-4 (0=All groups). Please choose a valid group.")
    end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    if not (unit == "percent" or unit == "dB") then
        error("Invalid unit '" .. tostring(unit) .. "'. Valid options are: 'percent' or 'dB'. Please choose a valid unit.")
    end
    local cmd = ""
    cmd = cmd .. "GROUP "
    cmd = cmd .. tostring(group)
    cmd = cmd .. " VOL"
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    cmd = cmd .. " "
    cmd = cmd .. tostring(level)
    if unit == "dB" and not (level == "+" or level == "-") then
        cmd = cmd .. " dB"
    end
    return cmd
end

function M.format_group_mute(args)
    -- Set group mute on or off.
    args = args or {}
    local group = args.group
    local mute = args.mute
    local channel = args.channel
    if channel == nil then channel = "LR" end
    if group < 0 or group > 4 then
        error("Invalid group number '" .. tostring(group) .. "'. Group must be between 0-4 (0=All groups). Please choose a valid group.")
    end
    if not (channel == "L" or channel == "R" or channel == "LR") then
        error("Invalid channel '" .. tostring(channel) .. "'. Valid options are: L (Left), R (Right), or LR (Both). Please choose a valid channel.")
    end
    local cmd = ""
    cmd = cmd .. "GROUP "
    cmd = cmd .. tostring(group)
    cmd = cmd .. " MUTE"
    if channel ~= "LR" then
        cmd = cmd .. " " .. tostring(channel)
    end
    if mute then
        cmd = cmd .. " ON"
    end
    if not mute then
        cmd = cmd .. " OFF"
    end
    return cmd
end

return M
