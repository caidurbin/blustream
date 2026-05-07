-- Lua ProxyHandler — Control4 audio_matrix_switch proxy glue.
--
-- Sits between Composer's ReceivedFromProxy callback and the
-- ConnectionStateMachine. Translates SELECT_AUDIO_DEVICE proxy commands
-- (the only verb the audio_matrix_switch proxy emits for routing) into
-- OUT/FR (or OUT/REM) wire strings via the codegen-emitted formatters in
-- generated.lua, enqueues each on the connection's FIFO send queue, and
-- records the commanded routing on the shared OptimisticStateTracker
-- (with the current monotonic time) so subsequent get_routing() calls
-- reflect the latest commanded state and the tracker's per-output 2s
-- lockout window keeps a stale STATUS poll from undoing it.
--
-- Per ADR-0003 the matrix exposes 16 stereo input bindings (1001..1016)
-- and 8 stereo output bindings (2001..2008) on the LR pair only; bus
-- channels and independent L/R control stay hidden behind the device's
-- web GUI. This module accordingly never threads channel arguments into
-- the formatters — defaulting to LR is what makes the binding shape
-- match the proxy contract.
--
-- Deliberately does not own:
--   * the lockout-window arithmetic itself (lives in optimistic_tracker.lua),
--   * STATUS poll reconciliation / diff-and-notify (polling_coordinator.lua),
--   * volume / mute / power (out of scope per ADR-0003).
--
-- The connection and tracker dependencies are injected so busted specs
-- can mock the transport surface; production code in driver.lua passes
-- the live ConnectionStateMachine and the tracker shared with the
-- PollingCoordinator.

local generated = require("generated")
local optimistic_tracker = require("optimistic_tracker")

local M = {}

-- Binding ID layout — keep in lockstep with control4/dmp168/src/driver.xml.
M.OUTPUT_BINDING_BASE = 2001
M.OUTPUT_COUNT = 8
M.INPUT_BINDING_BASE = 1001
M.INPUT_COUNT = 16

-- BINDID = 0 is Composer's documented "unbind" sentinel for the
-- audio_matrix_switch proxy: the user de-selected the source for the
-- output without picking a new one.
local UNBIND_SENTINEL = 0

local PH = {}
PH.__index = PH

local function noop() end

-- Construct a proxy handler. Required opts:
--   connection   Object with a `send(self, wire)` method (the
--                ConnectionStateMachine in production; a recorder in tests).
-- Optional:
--   tracker      OptimisticStateTracker the handler shares with the polling
--                coordinator. If omitted, the handler creates a private
--                tracker so older call sites (and unit tests that don't care
--                about the lockout window) keep working unchanged.
--   now_ms       Monotonic clock returning milliseconds. Used to stamp every
--                command's lockout reference time. Defaults to () -> 0 — fine
--                without a polling coordinator, which is the only consumer of
--                the timestamp.
--   log          Function called with a single string when debug_mode is on.
--   debug_mode   Boolean; gates verbose logging.
function M.new(opts)
    assert(opts, "proxy_handler.new requires an options table")
    assert(opts.connection, "proxy_handler.new: connection is required")

    local self = setmetatable({}, PH)
    self._conn = opts.connection
    self._log = opts.log or noop
    self._debug_mode = opts.debug_mode and true or false
    self._tracker = opts.tracker or optimistic_tracker.new()
    self._now_ms = opts.now_ms or function() return 0 end
    return self
end

-- ---------- inspection / configuration ----------

-- Snapshot of the optimistic routing table. Output indices are 1..8;
-- absent outputs are simply missing keys (treat as unrouted).
function PH:get_routing()
    return self._tracker:get_routing()
end

function PH:set_debug_mode(enabled)
    self._debug_mode = enabled and true or false
end

-- ---------- internal helpers ----------

function PH:_emit(msg)
    if self._debug_mode then
        self._log(msg)
    end
end

local function output_index_from_binding(binding)
    if type(binding) ~= "number" then return nil end
    local idx = binding - M.OUTPUT_BINDING_BASE + 1
    if idx < 1 or idx > M.OUTPUT_COUNT then return nil end
    return idx
end

local function input_index_from_binding(binding)
    if type(binding) == "string" then binding = tonumber(binding) end
    if type(binding) ~= "number" then return nil end
    if binding == UNBIND_SENTINEL then return UNBIND_SENTINEL end
    local idx = binding - M.INPUT_BINDING_BASE + 1
    if idx < 1 or idx > M.INPUT_COUNT then return nil end
    return idx
end

-- ---------- proxy command dispatch ----------

-- Composer's ReceivedFromProxy entry point feeds straight in here.
-- Unknown verbs are silently ignored — the audio_matrix_switch proxy
-- emits a small set, but Composer occasionally fires others (e.g. probes
-- on driver load) that the matrix has nothing to do with.
function PH:on_proxy_command(idBinding, strCommand, tParams)
    if strCommand == "SELECT_AUDIO_DEVICE" then
        self:_handle_select(idBinding, tParams or {})
    end
end

function PH:_handle_select(idBinding, tParams)
    local output = output_index_from_binding(idBinding)
    if not output then
        self:_emit("SELECT_AUDIO_DEVICE ignored: not an output binding " ..
            tostring(idBinding))
        return
    end

    local input = input_index_from_binding(tParams.BINDID)
    if input == nil then
        self:_emit("SELECT_AUDIO_DEVICE ignored: bad BINDID " ..
            tostring(tParams.BINDID))
        return
    end

    if input == UNBIND_SENTINEL then
        self:_unroute(output)
    else
        self:_route(output, input)
    end
end

function PH:_route(output, input)
    local wire = generated.format_route({ output = output, input_ch = input })
    self:_emit(("route output %d <- input %d (%s)"):format(output, input, wire))
    self._conn:send(wire)
    -- Optimistic update: reflect the commanded state immediately so
    -- subsequent reads (and the polling coordinator's diff check) see
    -- the new mapping without waiting for the device's STATUS response.
    -- The timestamp arms the per-output 2s lockout window in the tracker.
    self._tracker:note_command(output, input, self._now_ms())
end

function PH:_unroute(output)
    local prev = self._tracker:get_routing()[output]
    if prev == nil then
        -- Already unrouted; no wire command to send. The matrix's REM
        -- requires the source-input number, so we cannot synthesize one
        -- from thin air — and there's nothing to undo anyway.
        self:_emit(("unroute output %d skipped: already unrouted"):format(output))
        return
    end
    local wire = generated.format_output_remove({ output = output, input_ch = prev })
    self:_emit(("unroute output %d (was input %d): %s"):format(output, prev, wire))
    self._conn:send(wire)
    self._tracker:note_command(output, nil, self._now_ms())
end

return M
