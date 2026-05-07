-- Lua PollingCoordinator — periodic STATUS polling + diff-based notifications.
--
-- Owns the background loop described in ADR-0004: every Poll Interval (s)
-- (default 15, range 5..60), enqueue "STATUS" on the connection state
-- machine, then on the parsed STATUS response diff it against the
-- OptimisticStateTracker's view of routing. Every output that changed
-- becomes a single `on_routing_change(output, prev_input, new_input)`
-- callback to the driver shell, which translates it into the matching
-- C4:SendToProxy notification so bound Rooms / UI elements update.
--
-- This module deliberately holds no `C4:*` references and no I/O. Timer
-- and connection surfaces are injected so busted specs can drive the
-- loop deterministically; the driver passes thin wrappers around
-- C4:SetTimer / KillTimer and the live ConnectionStateMachine in
-- production.
--
-- The lockout window is owned by the OptimisticStateTracker (see
-- src/optimistic_tracker.lua); the coordinator just hands off the polled
-- snapshot and the current monotonic time to it. That keeps the
-- temporally-tricky logic in one pure module.

local M = {}

-- Default poll interval (ADR-0004; matches the Composer Property default).
M.DEFAULT_INTERVAL_MS = 15000

-- Composer's RANGED_INTEGER widget caps the Property at 5..60s, but we
-- defensively clamp at the boundary so a hand-edited project.c4p can't
-- shove a 0-second poll through and DOS the matrix.
local MIN_INTERVAL_MS = 5000
local MAX_INTERVAL_MS = 60000

local PC = {}
PC.__index = PC

local function noop() end

-- opts:
--   connection         Object with `:send(wire)`. Required.
--   timer              { set_timer(ms, cb) -> token, cancel_timer(token) }. Required.
--   tracker            OptimisticStateTracker instance. Required.
--   interval_ms        Initial poll interval. Defaults to 15000.
--   on_routing_change  function(output, prev_input, new_input). Defaults to noop.
--   now_ms             Monotonic clock function returning ms. Defaults to () -> 0
--                      (tests inject a controlled clock; the driver passes a
--                      wrapper around os.time()*1000 or a Composer monotonic).
--   log                Function called with a string when debug_mode is on.
--   debug_mode         Boolean.
function M.new(opts)
    assert(opts, "polling_coordinator.new requires an options table")
    assert(opts.connection, "polling_coordinator.new: connection is required")
    assert(opts.timer, "polling_coordinator.new: timer is required")
    assert(opts.tracker, "polling_coordinator.new: tracker is required")

    local self = setmetatable({}, PC)
    self._connection = opts.connection
    self._timer = opts.timer
    self._tracker = opts.tracker
    self._interval_ms = opts.interval_ms or M.DEFAULT_INTERVAL_MS
    self._on_routing_change = opts.on_routing_change or noop
    self._now_ms = opts.now_ms or function() return 0 end
    self._log = opts.log or noop
    self._debug_mode = opts.debug_mode and true or false

    self._running = false
    self._timer_token = nil
    return self
end

-- ---------- configuration ----------

function PC:set_interval_ms(ms)
    if type(ms) ~= "number" then return end
    if ms < MIN_INTERVAL_MS then ms = MIN_INTERVAL_MS end
    if ms > MAX_INTERVAL_MS then ms = MAX_INTERVAL_MS end
    self._interval_ms = ms
end

function PC:set_debug_mode(enabled)
    self._debug_mode = enabled and true or false
end

-- ---------- internal helpers ----------

function PC:_emit(msg)
    if self._debug_mode then self._log(msg) end
end

function PC:_cancel_timer()
    if self._timer_token ~= nil then
        if self._timer.cancel_timer then
            self._timer.cancel_timer(self._timer_token)
        end
        self._timer_token = nil
    end
end

function PC:_arm()
    if not self._running then return end
    self:_cancel_timer()
    self:_emit(("poll scheduled in %d ms"):format(self._interval_ms))
    self._timer_token = self._timer.set_timer(self._interval_ms, function()
        self._timer_token = nil
        self:_fire()
    end)
end

function PC:_fire()
    if not self._running then return end
    self:_emit("poll: STATUS")
    self._connection:send("STATUS")
    self:_arm()
end

-- ---------- lifecycle ----------

function PC:start()
    if self._running then return end
    self._running = true
    self:_arm()
end

function PC:stop()
    self._running = false
    self:_cancel_timer()
end

-- One-shot STATUS — the Refresh Matrix State Composer Action calls here
-- (or routes through the connection) so the manual poll re-uses the same
-- diff path as the periodic one. The next periodic poll re-arms relative
-- to *now* so the matrix isn't double-pummeled inside one interval.
function PC:refresh_now()
    self:_emit("poll (manual): STATUS")
    self._connection:send("STATUS")
    if self._running then self:_arm() end
end

-- ---------- diff + notify ----------

-- Collapse the parser's per-channel routing rows into a single
-- {[output] = input | nil} table. The audio_matrix_switch proxy is
-- channel-locked (ADR-0003) so we only consider the L row; the matrix
-- guarantees R follows L in normal operation, and a divergence is a
-- web-GUI configuration the proxy doesn't model anyway.
local function collapse_routing(rows)
    local polled = {}
    for _, row in ipairs(rows) do
        if row.channel == "L" then
            polled[row.output] = row.from_input
        end
    end
    return polled
end

-- Driver dispatches the parsed STATUS response here. The coordinator
-- collapses the per-channel rows into a per-output snapshot, hands it
-- to the tracker for lockout-aware reconciliation, and fires one
-- routing-change notification per actual diff.
function PC:on_status(parsed)
    if parsed == nil then return end
    local rows = parsed.routing
    if rows == nil then return end

    local polled = collapse_routing(rows)
    local now = self._now_ms()
    local changes = self._tracker:reconcile(polled, now)
    for _, change in ipairs(changes) do
        self:_emit(("notify out=%d prev=%s new=%s"):format(
            change.output,
            tostring(change.prev_input),
            tostring(change.new_input)
        ))
        self._on_routing_change(change.output, change.prev_input, change.new_input)
    end
end

return M
