-- Lua OptimisticStateTracker — pure logic for the optimistic-update +
-- 2-second-lockout contract from ADR-0004.
--
-- Decides, given (current routing, per-output command timestamps, current
-- monotonic time, polled snapshot), which outputs adopt a polled value
-- (the matrix is the source of truth) and which stay pinned to their
-- most-recent commanded value because the lockout window has not yet
-- expired. The tracker has no Composer dependencies and no I/O — it's
-- safe to require from busted specs and from the Composer Lua sandbox.
--
-- Time is always passed in by the caller in milliseconds; the tracker
-- never reads a clock itself. That keeps boundary cases (exactly 2000 ms
-- after a command) deterministic in tests and lets the polling
-- coordinator share a single clock source with the rest of the driver.
--
-- Routing snapshots and polled snapshots are both shaped as
--   { [output_index_1based] = input_index_1based | nil }
-- where a missing key (or an explicit nil) means the output is unrouted.
-- The tracker does not interpret L/R channels — the polling coordinator
-- is responsible for collapsing the parser's per-channel rows into a
-- single per-output value (channel-lock is always on per ADR-0003).

local M = {}

-- ADR-0004: ~2 seconds. The boundary at exactly lockout_ms is treated as
-- OUTSIDE the window — poll wins — so the lockout is half-open: [t, t+L).
M.DEFAULT_LOCKOUT_MS = 2000

local OST = {}
OST.__index = OST

-- opts:
--   lockout_ms (optional)   Lockout window in milliseconds. Defaults to 2000.
function M.new(opts)
    opts = opts or {}
    local self = setmetatable({}, OST)
    self._lockout_ms = opts.lockout_ms or M.DEFAULT_LOCKOUT_MS
    self._routing = {}            -- {[output] = input | nil}
    self._last_command_at = {}    -- {[output] = time_ms} for the most recent command
    return self
end

-- ---------- inspection ----------

-- Snapshot of the current reconciled routing. The returned table is
-- detached from internal state — mutating it has no effect on the tracker.
function OST:get_routing()
    local snap = {}
    for k, v in pairs(self._routing) do
        snap[k] = v
    end
    return snap
end

-- True iff `output` is within its 2-second post-command lockout at `time_ms`.
-- Half-open: a sample at exactly last_command_at + lockout_ms is OUTSIDE the
-- window. Outputs that have never received a command are never locked.
function OST:is_locked(output, time_ms)
    local t = self._last_command_at[output]
    if t == nil then return false end
    return (time_ms - t) < self._lockout_ms
end

-- ---------- mutation ----------

-- Record a commanded routing change for `output` at `time_ms`. Subsequent
-- reconcile() calls with a `time_ms` value less than `time_ms +
-- lockout_ms` will not override `input` for `output`. Pass `input = nil`
-- to record an unroute. A second call resets the lockout reference time
-- for `output` to the new `time_ms` (most-recent-wins).
function OST:note_command(output, input, time_ms)
    self._routing[output] = input
    self._last_command_at[output] = time_ms
end

-- ---------- reconciliation ----------

-- Apply a polled routing snapshot at `time_ms`. Outputs whose lockout
-- window has not yet expired keep their commanded state; all others
-- adopt the polled value (or nil = unrouted).
--
-- Returns a list of `{ output = n, prev_input = a|nil, new_input = b|nil }`
-- entries — one per output whose reconciled value changed. The polling
-- coordinator turns each entry into a proxy notification so bound Rooms
-- and UI elements update.
function OST:reconcile(polled, time_ms)
    polled = polled or {}
    local changes = {}

    -- Walk the union of outputs that exist in either the current routing
    -- or the polled snapshot. The polled side might surface an output the
    -- tracker has never seen (out-of-band routing); the current side might
    -- have an output the polled snapshot omits (unroute via web GUI).
    local seen = {}
    for k in pairs(self._routing) do seen[k] = true end
    for k in pairs(polled) do seen[k] = true end

    for output in pairs(seen) do
        if not self:is_locked(output, time_ms) then
            local prev = self._routing[output]
            local new = polled[output]
            if prev ~= new then
                self._routing[output] = new
                table.insert(changes, {
                    output = output,
                    prev_input = prev,
                    new_input = new,
                })
            end
        end
    end

    return changes
end

return M
