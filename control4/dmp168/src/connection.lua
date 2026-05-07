-- Lua ConnectionStateMachine — TCP lifecycle for the DMP168.
--
-- Owns the OFFLINE / CONNECTING / ONLINE state machine, the FIFO command
-- queue (one in-flight at a time), the reconnect-with-backoff loop, and the
-- on-connect init sequence (PON / STANDBY 0 / AUTO STB 0 / STATUS) that
-- wakes the device and seeds driver state.
--
-- This module deliberately has no `C4:*` references. Production code in
-- driver.lua passes thin wrappers around `C4:CreateNetworkConnection`,
-- `C4:NetConnect`, `C4:SendToNetwork`, and `C4:SetTimer` as the `net` and
-- `timer` deps; busted specs pass mocks that record calls. Keeps the
-- testable logic separate from the Composer-bound surface.
--
-- Polling, the optimistic state tracker, and the routing proxy handler
-- live in later slices and are not concerns of this module — see
-- docs/control4-driver-plan.md, phase 2.

local M = {}

-- Reconnect backoff schedule per ADR-0005 / issue #20: 1s, 2s, 5s, 15s,
-- then 30s steady. Last entry repeats indefinitely once exhausted.
M.BACKOFF_SCHEDULE_MS = { 1000, 2000, 5000, 15000, 30000 }

-- Wire-level init sequence issued, in order, on every transition to
-- ONLINE. PON wakes from POFF/Sleep/Standby; STANDBY 0 selects Sleep mode
-- so the network listener stays alive; AUTO STB 0 disables the auto-
-- standby timer so the device cannot drift off-line on its own; STATUS
-- seeds driver state.
M.INIT_SEQUENCE = { "PON", "STANDBY 0", "AUTO STB 0", "STATUS" }

local STATES = {
    OFFLINE = "OFFLINE",
    CONNECTING = "CONNECTING",
    ONLINE = "ONLINE",
}
M.STATES = STATES

local CSM = {}
CSM.__index = CSM

local function noop() end

-- Construct a state machine. Required opts:
--   binding_id      Control4 network-binding id passed to CreateNetworkConnection.
--   host            IP address or hostname for the matrix.
--   net             { create_network_connection, net_connect, net_disconnect,
--                     send_to_network } — mirror C4: methods of the same name.
--   timer           { set_timer, cancel_timer } — wraps C4:SetTimer / KillTimer.
-- Optional:
--   port            Defaults to 8000 (ADR-0005).
--   terminator      Wire-line terminator. Defaults to "\r\n".
--   log             Function called with a single string when debug_mode is on.
--   debug_mode      Boolean; gates verbose logging.
function M.new(opts)
    assert(opts, "connection.new requires an options table")
    assert(opts.binding_id, "connection.new: binding_id is required")
    assert(opts.net, "connection.new: net dependencies are required")
    assert(opts.timer, "connection.new: timer dependencies are required")

    local self = setmetatable({}, CSM)
    self._binding_id = opts.binding_id
    self._host = opts.host
    self._port = opts.port or 8000
    self._net = opts.net
    self._timer = opts.timer
    self._terminator = opts.terminator or "\r\n"
    self._log = opts.log or noop
    self._debug_mode = opts.debug_mode and true or false

    self._state = STATES.OFFLINE
    self._queue = {}
    self._inflight = false
    self._buffer = ""
    self._created = false
    self._reconnect_idx = 0   -- index into BACKOFF_SCHEDULE_MS for the *next* attempt
    self._reconnect_token = nil
    return self
end

-- ---------- inspection ----------

function CSM:get_state()
    return self._state
end

-- ---------- configuration ----------

function CSM:set_host(host)
    self._host = host
end

function CSM:set_port(port)
    self._port = port
end

function CSM:set_debug_mode(enabled)
    self._debug_mode = enabled and true or false
end

-- ---------- internal helpers ----------

function CSM:_emit(msg)
    if self._debug_mode then
        self._log(msg)
    end
end

function CSM:_set_state(s)
    if self._state == s then return end
    self:_emit("state " .. self._state .. " -> " .. s)
    self._state = s
end

function CSM:_cancel_reconnect()
    if self._reconnect_token ~= nil then
        if self._timer.cancel_timer then
            self._timer.cancel_timer(self._reconnect_token)
        end
        self._reconnect_token = nil
    end
end

-- Push the init sequence to the FRONT of the queue so it always fires
-- before any user commands queued while OFFLINE/CONNECTING. Order is
-- preserved: PON, then STANDBY 0, then AUTO STB 0, then STATUS, then
-- whatever the caller had already enqueued.
function CSM:_prepend_init_sequence()
    local merged = {}
    for _, cmd in ipairs(M.INIT_SEQUENCE) do
        table.insert(merged, cmd)
    end
    for _, cmd in ipairs(self._queue) do
        table.insert(merged, cmd)
    end
    self._queue = merged
end

function CSM:_pump()
    if self._state ~= STATES.ONLINE then return end
    if self._inflight then return end
    if #self._queue == 0 then return end
    local cmd = table.remove(self._queue, 1)
    self._inflight = true
    self:_emit("send: " .. cmd)
    self._net.send_to_network(self._binding_id, self._port, cmd .. self._terminator)
end

-- ---------- lifecycle ----------

-- Open the TCP connection. The first call also registers the network
-- binding via CreateNetworkConnection; subsequent calls (e.g. from the
-- reconnect timer) only reissue NetConnect — the binding is created once
-- per driver lifetime.
function CSM:start()
    if not self._created then
        self:_emit("create network connection -> " .. tostring(self._host))
        self._net.create_network_connection(self._binding_id, self._host)
        self._created = true
    end
    self:_cancel_reconnect()
    self:_set_state(STATES.CONNECTING)
    self:_emit("connect " .. tostring(self._host) .. ":" .. tostring(self._port))
    self._net.net_connect(self._binding_id, self._port)
end

function CSM:stop()
    self:_cancel_reconnect()
    if self._state ~= STATES.OFFLINE then
        if self._net.net_disconnect then
            self._net.net_disconnect(self._binding_id, self._port)
        end
        self:_set_state(STATES.OFFLINE)
    end
    self._inflight = false
    self._buffer = ""
end

-- ---------- C4 callbacks ----------

-- Composer fires this when the underlying TCP socket transitions. The two
-- statuses that matter to the state machine are "ONLINE" and "OFFLINE";
-- anything else (e.g. "CONNECTING") is treated as a no-op.
function CSM:on_connection_status(status)
    if status == "ONLINE" then
        if self._state == STATES.ONLINE then return end
        self._reconnect_idx = 0
        self:_cancel_reconnect()
        self:_set_state(STATES.ONLINE)
        self._inflight = false
        self._buffer = ""
        self:_prepend_init_sequence()
        self:_pump()
    elseif status == "OFFLINE" then
        self._inflight = false
        self._buffer = ""
        if self._state ~= STATES.OFFLINE then
            self:_set_state(STATES.OFFLINE)
        end
        self:_schedule_reconnect()
    end
end

-- Bytes from Composer's NetReceive callback. The state machine only cares
-- that *some* line came back so it can release the in-flight slot and
-- send the next queued command. Parsing is the status_parser's job and
-- happens in a later slice.
function CSM:on_received(data)
    self._buffer = self._buffer .. data
    while true do
        local _, end_idx = self._buffer:find("\r?\n", 1)
        if not end_idx then break end
        self._buffer = self._buffer:sub(end_idx + 1)
        self._inflight = false
    end
    self:_pump()
end

-- ---------- queue API ----------

-- Enqueue a fully-formed wire string (no terminator — the state machine
-- appends it). Pumps immediately if the link is ONLINE and idle.
function CSM:send(wire)
    table.insert(self._queue, wire)
    self:_pump()
end

-- One-shot STATUS poll triggered by the Refresh Matrix State Composer
-- action. If the link is currently OFFLINE, the request waits in the
-- queue and dispatches after the init sequence on the next ONLINE.
function CSM:refresh_matrix_state()
    self:send("STATUS")
end

-- ---------- reconnect ----------

function CSM:_schedule_reconnect()
    self:_cancel_reconnect()
    local idx = math.min(self._reconnect_idx + 1, #M.BACKOFF_SCHEDULE_MS)
    local delay = M.BACKOFF_SCHEDULE_MS[idx]
    self._reconnect_idx = idx
    self:_emit(("reconnect scheduled in %d ms (attempt %d)"):format(delay, idx))
    self._reconnect_token = self._timer.set_timer(delay, function()
        self._reconnect_token = nil
        if self._state == STATES.OFFLINE then
            self:start()
        end
    end)
end

return M
