-- Tests for the Lua PollingCoordinator.
--
-- The coordinator owns the periodic STATUS poll loop: a timer fires every
-- `Poll Interval (s)`, the coordinator enqueues "STATUS" on the connection,
-- and incoming parsed STATUS responses are diffed (through the optimistic
-- tracker) against internal state. Each output that changed is reported
-- via an injected callback so the driver shell can fire the matching
-- C4:SendToProxy notification — the unit tests only need to assert that
-- the callback fired with the right (output, prev, new) tuple. See ADR-0004
-- and issue #22.
--
-- Time and the timer surface are mocked here so the test never blocks on
-- a wall-clock delay; the harness drives the simulated clock and fires
-- pending timers explicitly.

package.path = "control4/dmp168/src/?.lua;" .. package.path

local polling_coordinator = require("polling_coordinator")
local optimistic_tracker = require("optimistic_tracker")

local function make_harness(opts)
    opts = opts or {}
    local h = {
        sent = {},
        timers = {},
        timer_seq = 0,
        log_messages = {},
        notifications = {},
        now = opts.start_now or 0,
    }

    h.connection = {
        send = function(self, wire)  -- luacheck: no unused args
            table.insert(h.sent, wire)
        end,
    }

    h.timer = {
        set_timer = function(ms, callback)
            h.timer_seq = h.timer_seq + 1
            local id = h.timer_seq
            h.timers[id] = { id = id, ms = ms, callback = callback, cancelled = false }
            return id
        end,
        cancel_timer = function(id)
            if h.timers[id] then h.timers[id].cancelled = true end
        end,
    }

    h.log = function(msg) table.insert(h.log_messages, msg) end

    h.tracker = opts.tracker or optimistic_tracker.new()

    h.pc = polling_coordinator.new({
        connection = h.connection,
        timer = h.timer,
        tracker = h.tracker,
        interval_ms = opts.interval_ms,
        on_routing_change = function(output, prev_input, new_input)
            table.insert(h.notifications, {
                output = output,
                prev_input = prev_input,
                new_input = new_input,
            })
        end,
        now_ms = function() return h.now end,
        log = h.log,
        debug_mode = opts.debug_mode,
    })

    function h:advance(ms)
        self.now = self.now + ms
    end

    function h:fire_pending_timer()
        local target
        for _, t in pairs(self.timers) do
            if not t.cancelled and not t.fired then
                if not target or t.id > target.id then target = t end
            end
        end
        assert(target, "no pending timer to fire")
        target.fired = true
        target.callback()
    end

    return h
end

local function status_with_routing(routing)
    -- Build a fake parsed STATUS state in the same shape that
    -- status_parser.parse() returns, with one (L, R) row per output entry
    -- so the coordinator's L-channel filter is exercised faithfully.
    local rows = {}
    for output = 1, 8 do
        local from_input = routing[output]
        table.insert(rows, { output = output, channel = "L", from_input = from_input })
        table.insert(rows, { output = output, channel = "R", from_input = from_input })
    end
    return { routing = rows, power = "On" }
end

describe("PollingCoordinator", function()
    describe("construction", function()
        it("requires a connection and a timer", function()
            assert.has_error(function()
                polling_coordinator.new({ timer = {} })
            end)
            assert.has_error(function()
                polling_coordinator.new({ connection = {} })
            end)
        end)

        it("defaults the poll interval to 15s (Composer Property default)", function()
            assert.are.equal(15000, polling_coordinator.DEFAULT_INTERVAL_MS)
        end)

        it("does not arm any timer until start() is called", function()
            local h = make_harness()
            assert.are.equal(0, h.timer_seq)
        end)
    end)

    describe("start() / stop() — timer lifecycle", function()
        it("arms a timer at the configured interval on start()", function()
            local h = make_harness({ interval_ms = 15000 })
            h.pc:start()
            assert.are.equal(1, h.timer_seq)
            assert.are.equal(15000, h.timers[1].ms)
        end)

        it("issues STATUS on every timer fire and re-arms the next poll", function()
            local h = make_harness({ interval_ms = 15000 })
            h.pc:start()
            h:fire_pending_timer()
            assert.are.same({ "STATUS" }, h.sent)
            assert.are.equal(2, h.timer_seq)
            assert.are.equal(15000, h.timers[2].ms)

            h:fire_pending_timer()
            assert.are.same({ "STATUS", "STATUS" }, h.sent)
            assert.are.equal(3, h.timer_seq)
        end)

        it("is idempotent across repeated start() calls", function()
            local h = make_harness()
            h.pc:start()
            h.pc:start()
            assert.are.equal(1, h.timer_seq)
        end)

        it("stop() cancels the pending timer and halts STATUS issuance", function()
            local h = make_harness()
            h.pc:start()
            h.pc:stop()
            assert.is_true(h.timers[1].cancelled)
            -- A re-fire of an already-cancelled timer must not produce a
            -- STATUS write, because stop() flips the running flag.
            h.timers[1].callback()
            assert.are.same({}, h.sent)
        end)
    end)

    describe("set_interval_ms() — Composer Property changes", function()
        it("uses the new interval on the next re-arm", function()
            local h = make_harness({ interval_ms = 15000 })
            h.pc:start()
            h.pc:set_interval_ms(5000)
            h:fire_pending_timer()  -- still 15s timer was armed; fires + re-arms at new interval
            assert.are.equal(5000, h.timers[2].ms)
        end)

        it("clamps below 5s up to 5s (matches RANGED_INTEGER 5..60)", function()
            local h = make_harness()
            h.pc:set_interval_ms(1)
            h.pc:start()
            assert.are.equal(5000, h.timers[1].ms)
        end)

        it("clamps above 60s down to 60s", function()
            local h = make_harness()
            h.pc:set_interval_ms(120000)
            h.pc:start()
            assert.are.equal(60000, h.timers[1].ms)
        end)
    end)

    describe("on_status() — diff + notify", function()
        it("fires no notifications when the polled state matches internal state", function()
            local h = make_harness()
            -- Seed the tracker so the polled snapshot equals current state.
            h.tracker:reconcile({ [1] = 5, [2] = 7 }, 0)
            h:advance(10000)  -- past any plausible lockout
            h.pc:on_status(status_with_routing({ [1] = 5, [2] = 7 }))
            assert.are.same({}, h.notifications)
        end)

        it("fires one notification per changed output", function()
            local h = make_harness()
            h.tracker:reconcile({ [1] = 1, [2] = 2, [3] = 3 }, 0)
            h:advance(10000)
            h.pc:on_status(status_with_routing({ [1] = 9, [2] = 2, [3] = 7 }))

            table.sort(h.notifications, function(a, b) return a.output < b.output end)
            assert.are.same(
                {
                    { output = 1, prev_input = 1, new_input = 9 },
                    { output = 3, prev_input = 3, new_input = 7 },
                },
                h.notifications
            )
        end)

        it("collapses L/R channel rows into one diff per output", function()
            local h = make_harness()
            -- Status parser emits a row per L/R channel; the coordinator
            -- only diffs on the L channel because the proxy is channel-locked.
            local parsed = {
                routing = {
                    { output = 1, channel = "L", from_input = 5 },
                    { output = 1, channel = "R", from_input = 99 },  -- ignored
                },
                power = "On",
            }
            h:advance(10000)
            h.pc:on_status(parsed)
            assert.are.same(
                { { output = 1, prev_input = nil, new_input = 5 } },
                h.notifications
            )
        end)

        it("treats from_input=nil in the parsed routing as an unroute", function()
            local h = make_harness()
            h.tracker:reconcile({ [1] = 5 }, 0)
            h:advance(10000)
            local parsed = {
                routing = {
                    { output = 1, channel = "L", from_input = nil },
                    { output = 1, channel = "R", from_input = nil },
                },
                power = "On",
            }
            h.pc:on_status(parsed)
            assert.are.same(
                { { output = 1, prev_input = 5, new_input = nil } },
                h.notifications
            )
        end)

        it("ignores stale polls inside the lockout window for an output", function()
            local h = make_harness()
            h.tracker:note_command(1, 5, h.now)
            h.pc:on_status(status_with_routing({ [1] = 2 }))
            -- Inside the lockout: no diff fired, optimistic state survives.
            assert.are.same({}, h.notifications)
            assert.are.equal(5, h.tracker:get_routing()[1])
        end)

        it("accepts polls past the lockout window even on the same output", function()
            local h = make_harness()
            h.tracker:note_command(1, 5, h.now)
            h:advance(2000)  -- exactly at the boundary, half-open: poll wins
            h.pc:on_status(status_with_routing({ [1] = 9 }))
            assert.are.same(
                { { output = 1, prev_input = 5, new_input = 9 } },
                h.notifications
            )
        end)

        it("is a no-op when the parsed status has no routing section", function()
            local h = make_harness()
            h.pc:on_status({})
            h.pc:on_status({ routing = nil })
            h.pc:on_status(nil)
            assert.are.same({}, h.notifications)
        end)
    end)

    describe("refresh_now() — manual force-poll", function()
        it("issues STATUS immediately without waiting for the timer", function()
            local h = make_harness()
            h.pc:start()
            h.pc:refresh_now()
            assert.are.same({ "STATUS" }, h.sent)
        end)

        it("re-arms the timer relative to the manual poll", function()
            -- Otherwise a manual refresh + a timer fire shortly after would
            -- pummel the matrix with two STATUS writes inside the interval.
            local h = make_harness({ interval_ms = 15000 })
            h.pc:start()
            local first_token = h.timers[1].id
            h.pc:refresh_now()
            -- The original timer is cancelled and a fresh 15s timer armed.
            assert.is_true(h.timers[first_token].cancelled)
            assert.are.equal(15000, h.timers[h.timer_seq].ms)
        end)

        it("works even when the coordinator is not running", function()
            local h = make_harness()
            h.pc:refresh_now()
            assert.are.same({ "STATUS" }, h.sent)
        end)
    end)

    describe("Debug Mode", function()
        it("suppresses log output when debug_mode is false", function()
            local h = make_harness({ debug_mode = false })
            h.pc:start()
            h:fire_pending_timer()
            assert.are.equal(0, #h.log_messages)
        end)

        it("emits log output when debug_mode is true", function()
            local h = make_harness({ debug_mode = true })
            h.pc:start()
            h:fire_pending_timer()
            assert.is_true(#h.log_messages > 0)
        end)

        it("toggles at runtime via set_debug_mode()", function()
            local h = make_harness({ debug_mode = false })
            h.pc:start()
            h:fire_pending_timer()
            assert.are.equal(0, #h.log_messages)

            h.pc:set_debug_mode(true)
            h:fire_pending_timer()
            assert.is_true(#h.log_messages > 0)
        end)
    end)
end)
