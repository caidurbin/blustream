-- Blustream DMP168 Control4 driver entry point.
--
-- This file is the thin Composer-bound shell. The deep, testable logic
-- lives in:
--   * connection.lua          TCP lifecycle + FIFO queue + reconnect backoff
--   * proxy_handler.lua       audio_matrix_switch SELECT_AUDIO_DEVICE → wire
--   * optimistic_tracker.lua  routing state + 2s lockout reconciliation
--   * polling_coordinator.lua periodic STATUS poll + diff-based notifications
--   * status_parser.lua       multi-section STATUS text → structured state
--
-- driver.lua is responsible for:
--
--   * lifecycle hooks (OnDriverInit / OnDriverLateInit / OnDriverDestroyed),
--   * reading driver Properties (Host, Port, Debug Mode, Poll Interval (s)),
--   * binding the C4: namespace into the connection / coordinator,
--   * delivering Composer Action invocations (Refresh Matrix State),
--   * dispatching parsed STATUS responses into the polling coordinator,
--   * firing C4:SendToProxy notifications for diff-detected routing changes.
--
-- C4:AllowExecute(true) is injected by drivers-driverpackager when the
-- archive is built with -ae (the dev flavor); release builds omit it.
-- See tools/build_c4z.py.

local connection = require("connection")
local proxy_handler = require("proxy_handler")
local optimistic_tracker = require("optimistic_tracker")
local polling_coordinator = require("polling_coordinator")
local status_parser = require("status_parser")

local NETWORK_BINDING = 6001  -- matches <connection><id>6001</id></connection> in driver.xml
local OUTPUT_BINDING_BASE = 2001
local INPUT_BINDING_BASE = 1001

local DEFAULT_PORT = 8000
local DEFAULT_POLL_INTERVAL_S = 15
local DEFAULT_DEBUG_MODE = false

local cs = nil
local ph = nil
local tracker = nil
local pc = nil
local status_buffer = ""

local function now_ms()
    -- Composer exposes C4:GetTime() returning seconds since epoch on most
    -- firmwares; fall back to os.time() for the smoke specs that load this
    -- file outside the Composer sandbox. Multiply to milliseconds so the
    -- tracker's lockout arithmetic is in its native unit.
    if C4 ~= nil and type(C4.GetTime) == "function" then
        return C4:GetTime() * 1000
    end
    return os.time() * 1000
end

local function debug_log(msg)
    -- print() routes to the Composer Lua console under DriverWorks.
    print("[blustream-dmp168] " .. tostring(msg))
end

local function make_dependencies()
    local net = {
        create_network_connection = function(binding_id, host)
            C4:CreateNetworkConnection(binding_id, host)
        end,
        net_connect = function(binding_id, port)
            C4:NetConnect(binding_id, port)
        end,
        net_disconnect = function(binding_id, port)
            C4:NetDisconnect(binding_id, port)
        end,
        send_to_network = function(binding_id, port, data)
            C4:SendToNetwork(binding_id, port, data)
        end,
    }
    local timer = {
        set_timer = function(ms, callback)
            -- Composer's SetTimer signature: (durationMs, callback, repeating).
            -- The state machine arms one-shot timers, so repeating=false.
            return C4:SetTimer(ms, callback, false)
        end,
        cancel_timer = function(token)
            if token ~= nil then
                C4:KillTimer(token)
            end
        end,
    }
    return net, timer
end

local function read_property(name, default)
    -- Properties[<name>] is the Composer-populated table the driver reads.
    -- During very early init Properties may be nil; fall back to the
    -- default in that case rather than throwing inside OnDriverLateInit.
    if Properties == nil then return default end
    local value = Properties[name]
    if value == nil or value == "" then return default end
    return value
end

local function read_port()
    local raw = read_property("Port", DEFAULT_PORT)
    local port = tonumber(raw)
    if port == nil then return DEFAULT_PORT end
    return port
end

local function read_debug_mode()
    local raw = read_property("Debug Mode", DEFAULT_DEBUG_MODE)
    if type(raw) == "boolean" then return raw end
    if type(raw) == "string" then
        local upper = raw:upper()
        return upper == "ON" or upper == "TRUE" or upper == "YES"
    end
    return DEFAULT_DEBUG_MODE
end

local function read_poll_interval()
    local raw = read_property("Poll Interval (s)", DEFAULT_POLL_INTERVAL_S)
    local n = tonumber(raw)
    if n == nil then return DEFAULT_POLL_INTERVAL_S end
    -- Composer LIST/RANGED widgets enforce the 5-60 range, but be defensive
    -- against hand-edits to project.c4p.
    if n < 5 then return 5 end
    if n > 60 then return 60 end
    return n
end

local function notify_routing_change(output, prev_input, new_input)  -- luacheck: no unused args
    -- Composer's audio_matrix_switch proxy reflects routing state via
    -- SendToProxy(<output_binding>, "SELECT_AUDIO_DEVICE", { BINDID = <input> }).
    -- BINDID = 0 is the documented unbind sentinel that bound Rooms inspect
    -- to clear their source selection.
    local out_binding = OUTPUT_BINDING_BASE + output - 1
    local input_binding
    if new_input == nil then
        input_binding = 0
    else
        input_binding = INPUT_BINDING_BASE + new_input - 1
    end
    if C4 ~= nil then
        C4:SendToProxy(out_binding, "SELECT_AUDIO_DEVICE", { BINDID = input_binding }, "NOTIFY")
    end
end

function OnDriverInit(driverInitType)  -- luacheck: no unused args
    -- Constructed up-front so the C4 callbacks below always have a valid
    -- target. Actual TCP work waits until OnDriverLateInit so Composer has
    -- finished populating Properties.
    local net, timer = make_dependencies()
    tracker = optimistic_tracker.new()
    cs = connection.new({
        binding_id = NETWORK_BINDING,
        host = read_property("Host", nil),
        port = read_port(),
        net = net,
        timer = timer,
        log = debug_log,
        debug_mode = read_debug_mode(),
    })
    ph = proxy_handler.new({
        connection = cs,
        tracker = tracker,
        now_ms = now_ms,
        log = debug_log,
        debug_mode = read_debug_mode(),
    })
    pc = polling_coordinator.new({
        connection = cs,
        timer = timer,
        tracker = tracker,
        interval_ms = read_poll_interval() * 1000,
        on_routing_change = notify_routing_change,
        now_ms = now_ms,
        log = debug_log,
        debug_mode = read_debug_mode(),
    })
end

function OnDriverLateInit(driverInitType)  -- luacheck: no unused args
    if cs == nil then return end
    cs:set_host(read_property("Host", nil))
    cs:set_port(read_port())
    cs:set_debug_mode(read_debug_mode())
    if pc ~= nil then
        pc:set_interval_ms(read_poll_interval() * 1000)
        pc:set_debug_mode(read_debug_mode())
    end
    cs:start()
    if pc ~= nil then pc:start() end
end

function OnDriverDestroyed()
    if pc ~= nil then
        pc:stop()
        pc = nil
    end
    if cs ~= nil then
        cs:stop()
        cs = nil
    end
    ph = nil
    tracker = nil
    status_buffer = ""
end

-- Composer fires this when a Property edit lands. Re-read the affected
-- value into the state machine so changes take effect without a driver
-- reload.
function OnPropertyChanged(strProperty)
    if cs == nil then return end
    if strProperty == "Host" then
        cs:set_host(read_property("Host", nil))
    elseif strProperty == "Port" then
        cs:set_port(read_port())
    elseif strProperty == "Debug Mode" then
        local enabled = read_debug_mode()
        cs:set_debug_mode(enabled)
        if ph ~= nil then ph:set_debug_mode(enabled) end
        if pc ~= nil then pc:set_debug_mode(enabled) end
    elseif strProperty == "Poll Interval (s)" then
        if pc ~= nil then pc:set_interval_ms(read_poll_interval() * 1000) end
    end
end

-- Composer's network event: status ∈ {"ONLINE", "OFFLINE"}.
function OnConnectionStatusChanged(idBinding, nPort, strStatus)  -- luacheck: no unused args
    if cs == nil then return end
    if idBinding ~= NETWORK_BINDING then return end
    cs:on_connection_status(strStatus)
end

-- Composer's network data callback. The state machine buffers and
-- splits on \r\n internally for inflight-slot accounting; we *also*
-- accumulate every byte into status_buffer here so a complete STATUS
-- response can be parsed and handed to the polling coordinator. The
-- parser tolerates trailing junk, so we attempt a parse on every chunk
-- and clear the buffer once a valid (non-empty routing) response lands.
function ReceivedFromNetwork(idBinding, nPort, strData)  -- luacheck: no unused args
    if cs == nil then return end
    if idBinding ~= NETWORK_BINDING then return end
    cs:on_received(strData)

    status_buffer = status_buffer .. strData
    local ok, parsed = pcall(status_parser.parse, status_buffer)
    if ok and parsed.routing and #parsed.routing > 0 then
        if pc ~= nil then pc:on_status(parsed) end
        status_buffer = ""
    end
end

-- Composer Action handlers. Action names are configured in driver.xml
-- under <actions>. ExecuteCommand receives them with the action name as
-- strCommand (no params for Refresh Matrix State).
function ExecuteCommand(strCommand, tParams)  -- luacheck: no unused args
    if strCommand == "Refresh Matrix State" or strCommand == "REFRESH_MATRIX_STATE" then
        -- Route through the polling coordinator so the next periodic poll
        -- re-arms relative to *now*, avoiding a double-pummel inside one
        -- interval. Falls through to the connection's queue if for some
        -- reason the coordinator hasn't been initialized yet.
        if pc ~= nil then
            pc:refresh_now()
        elseif cs ~= nil then
            cs:refresh_matrix_state()
        end
    end
end

-- Composer fires this on the relevant binding (typically an output
-- 2001..2008) when a Room programs a routing change. The proxy handler
-- translates SELECT_AUDIO_DEVICE into wire commands and enqueues them
-- via the connection state machine.
function ReceivedFromProxy(idBinding, strCommand, tParams)
    if ph == nil then return end
    ph:on_proxy_command(idBinding, strCommand, tParams)
end
