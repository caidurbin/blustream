-- Pure-function STATUS parser for the DMP168.
--
-- Mirrors blustream/devices/dmp168/status_parser.py: takes a raw STATUS
-- response string and returns a structured-state Lua table. The two
-- implementations are exercised by shared captured-response fixtures under
-- spec/vectors/fixtures/; CI fails the build if they diverge.
--
-- The function intentionally has no Control4 (`C4`) dependencies, no global
-- state, and no I/O — it's safe to require from busted specs and from the
-- Composer Lua sandbox alike.

local M = {}

local function split_lines(text)
    local lines = {}
    -- Append a trailing "\n" so the final line (if not newline-terminated) is
    -- still captured by the gmatch below.
    local padded = text .. "\n"
    for line in padded:gmatch("([^\r\n]*)\r?\n") do
        table.insert(lines, line)
    end
    return lines
end

local function strip(s)
    return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function split_ws(s)
    local parts = {}
    for token in s:gmatch("%S+") do
        table.insert(parts, token)
    end
    return parts
end

local function find_header(lines)
    for i, line in ipairs(lines) do
        if line:find("Power", 1, true) and line:find("Baud", 1, true) then
            return i
        end
    end
    return nil
end

local function parse_number(token, suffix)
    if suffix and #token >= #suffix and token:sub(-#suffix) == suffix then
        token = token:sub(1, -#suffix - 1)
    end
    return tonumber(token)
end

local function parse_system(lines)
    local header_idx = find_header(lines)
    if not header_idx or header_idx + 1 > #lines then
        error("STATUS response missing Power/Baud header line")
    end
    local data_line = lines[header_idx + 1]
    local parts = split_ws(data_line)
    if #parts < 8 then
        error(("STATUS data line has %d fields; expected at least 8"):format(#parts))
    end
    return {
        power = parts[1],
        baud = tonumber(parts[2]),
        level_unit = parts[3],
        auto_standby_time = tonumber(parts[4]),
        dsp_usage = parse_number(parts[5], "%"),
        fade = parts[6] == "On",
        temperature = parse_number(parts[7], "C"),
        uptime = parts[8],
    }
end

local function parse_firmware(lines)
    for _, line in ipairs(lines) do
        local idx = line:find("FW Version:", 1, true)
        if idx then
            local rest = strip(line:sub(idx + #"FW Version:"))
            -- Skip the welcome banner's bare "FW Version: 1.1.0" — prefer the
            -- structured "MCU_Main Vx.y.z/Web_GUI Vx.y.z" form from the
            -- status block.
            if rest:find("/", 1, true) or rest:find("_", 1, true) then
                return rest
            end
        end
    end
    return "Unknown"
end

local function parse_inputs(lines)
    local inputs = {}
    local in_section = false
    for _, line in ipairs(lines) do
        if line:find("Input Settings Status", 1, true) then
            in_section = true
        elseif in_section then
            local parts = split_ws(line)
            if #parts >= 6 then
                local port = parts[1]:match("^In(%d+)$")
                if port then
                    table.insert(inputs, {
                        port = tonumber(port),
                        lock = parts[2] == "On",
                        gain_l = tonumber(parts[3]),
                        gain_r = tonumber(parts[4]),
                        mute_l = parts[5] == "On",
                        mute_r = parts[6] == "On",
                    })
                end
            end
        end
    end
    return inputs
end

local function parse_routing(lines)
    local routing = {}
    local in_section = false
    for _, line in ipairs(lines) do
        if line:find("Matrix Config Status", 1, true) then
            in_section = true
        elseif in_section then
            local parts = split_ws(line)
            if #parts >= 2 then
                local output = parts[1]:match("^Out(%d+)$")
                if output then
                    local channel = parts[2]
                    if channel ~= "L" and channel ~= "R" then
                        channel = "L"
                    end
                    local from_input = nil
                    for i = 3, #parts do
                        local n = parts[i]:match("^In(%d+)$")
                        if n then
                            from_input = tonumber(n)
                            break
                        end
                    end
                    table.insert(routing, {
                        output = tonumber(output),
                        channel = channel,
                        from_input = from_input,
                    })
                end
            end
        end
    end
    return routing
end

function M.parse(response_text)
    local lines = split_lines(response_text)
    local result = parse_system(lines)
    result.firmware_version = parse_firmware(lines)
    result.inputs = parse_inputs(lines)
    result.routing = parse_routing(lines)
    return result
end

return M
