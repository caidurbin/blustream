-- Tests for the Lua ConnectionStateMachine.
--
-- The state machine is the single piece of Lua code that owns the TCP
-- lifecycle to the matrix. It binds to C4:CreateNetworkConnection and
-- C4:SetTimer in production but is constructed with injected `net` and
-- `timer` tables here so the tests can drive the network/timer surface
-- deterministically without a Composer sandbox. See issue #20.

package.path = "control4/dmp168/src/?.lua;" .. package.path

local connection = require("connection")

local BINDING = 6001

local function make_harness(opts)
    opts = opts or {}
    local h = {
        sent = {},
        net_calls = {},
        timers = {},
        timer_seq = 0,
        log_messages = {},
    }
    h.net = {
        create_network_connection = function(binding_id, host)
            table.insert(h.net_calls, { op = "create", binding = binding_id, host = host })
        end,
        net_connect = function(binding_id, port)
            table.insert(h.net_calls, { op = "connect", binding = binding_id, port = port })
        end,
        net_disconnect = function(binding_id, port)
            table.insert(h.net_calls, { op = "disconnect", binding = binding_id, port = port })
        end,
        send_to_network = function(binding_id, port, data)
            table.insert(h.sent, { binding = binding_id, port = port, data = data })
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
            if h.timers[id] then
                h.timers[id].cancelled = true
            end
        end,
    }
    h.log = function(msg) table.insert(h.log_messages, msg) end

    h.cs = connection.new({
        binding_id = BINDING,
        host = opts.host or "192.168.1.10",
        port = opts.port or 8000,
        net = h.net,
        timer = h.timer,
        log = h.log,
        debug_mode = opts.debug_mode,
    })

    function h:fire_pending_timer()
        -- Fire the most recently armed, not-yet-fired timer. Mimics what
        -- Composer would do once the wall-clock delay elapses.
        local target
        for _, t in pairs(self.timers) do
            if not t.cancelled and not t.fired then
                if not target or t.id > target.id then
                    target = t
                end
            end
        end
        assert(target, "no pending timer to fire")
        target.fired = true
        target.callback()
    end

    function h:wires_sent()
        local wires = {}
        for _, entry in ipairs(self.sent) do
            -- Trim the terminator so vector-style assertions stay readable.
            table.insert(wires, (entry.data:gsub("\r\n$", "")))
        end
        return wires
    end

    return h
end

describe("ConnectionStateMachine", function()
    describe("construction", function()
        it("starts in OFFLINE", function()
            local h = make_harness()
            assert.are.equal("OFFLINE", h.cs:get_state())
        end)

        it("exposes the canonical backoff schedule", function()
            assert.are.same(
                { 1000, 2000, 5000, 15000, 30000 },
                connection.BACKOFF_SCHEDULE_MS
            )
        end)

        it("exposes the canonical init sequence", function()
            assert.are.same(
                { "PON", "STANDBY 0", "AUTO STB 0", "STATUS" },
                connection.INIT_SEQUENCE
            )
        end)
    end)

    describe("start()", function()
        it("creates the network connection and transitions to CONNECTING", function()
            local h = make_harness({ host = "10.0.0.5", port = 8000 })
            h.cs:start()

            assert.are.equal("CONNECTING", h.cs:get_state())
            assert.are.equal("create", h.net_calls[1].op)
            assert.are.equal(BINDING, h.net_calls[1].binding)
            assert.are.equal("10.0.0.5", h.net_calls[1].host)
            assert.are.equal("connect", h.net_calls[2].op)
            assert.are.equal(BINDING, h.net_calls[2].binding)
            assert.are.equal(8000, h.net_calls[2].port)
        end)

        it("is idempotent on the create call across reconnects", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("OFFLINE")
            h:fire_pending_timer()  -- fires the 1s reconnect timer

            local creates = 0
            for _, call in ipairs(h.net_calls) do
                if call.op == "create" then creates = creates + 1 end
            end
            assert.are.equal(1, creates)
        end)
    end)

    describe("transition to ONLINE", function()
        it("fires the init sequence in order on ONLINE", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("ONLINE")

            assert.are.equal("ONLINE", h.cs:get_state())
            -- One in flight at a time means only the first ("PON") is on the
            -- wire until a response is received.
            assert.are.same({ "PON" }, h:wires_sent())

            h.cs:on_received("PON\r\n")
            assert.are.same({ "PON", "STANDBY 0" }, h:wires_sent())

            h.cs:on_received("OK\r\n")
            assert.are.same({ "PON", "STANDBY 0", "AUTO STB 0" }, h:wires_sent())

            h.cs:on_received("OK\r\n")
            assert.are.same(
                { "PON", "STANDBY 0", "AUTO STB 0", "STATUS" },
                h:wires_sent()
            )
        end)

        it("re-fires the full init sequence on every ONLINE", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            for _ = 1, 4 do h.cs:on_received("ack\r\n") end
            assert.are.equal(4, #h:wires_sent())

            -- Drop the link, reconnect, come ONLINE again.
            h.cs:on_connection_status("OFFLINE")
            h:fire_pending_timer()
            h.cs:on_connection_status("ONLINE")

            -- Pump out the second init sequence.
            for _ = 1, 4 do h.cs:on_received("ack\r\n") end

            assert.are.same(
                {
                    "PON", "STANDBY 0", "AUTO STB 0", "STATUS",
                    "PON", "STANDBY 0", "AUTO STB 0", "STATUS",
                },
                h:wires_sent()
            )
        end)
    end)

    describe("FIFO command queue", function()
        it("preserves enqueue order with one in-flight command at a time", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            -- Drain the init sequence first so the test is about user commands.
            for _ = 1, 4 do h.cs:on_received("ack\r\n") end

            h.cs:send("CMD_A")
            h.cs:send("CMD_B")
            h.cs:send("CMD_C")

            -- Only CMD_A is in flight initially.
            assert.are.equal("CMD_A", h:wires_sent()[5])
            assert.are.equal(5, #h:wires_sent())

            h.cs:on_received("ack\r\n")
            assert.are.equal("CMD_B", h:wires_sent()[6])
            assert.are.equal(6, #h:wires_sent())

            h.cs:on_received("ack\r\n")
            assert.are.equal("CMD_C", h:wires_sent()[7])
            assert.are.equal(7, #h:wires_sent())
        end)

        it("queues commands sent before ONLINE and flushes after init", function()
            local h = make_harness()
            h.cs:start()
            -- Queued while CONNECTING — must not hit the wire yet.
            h.cs:send("EARLY")
            assert.are.equal(0, #h:wires_sent())

            h.cs:on_connection_status("ONLINE")
            -- Init runs first; EARLY queues behind STATUS.
            for _ = 1, 4 do h.cs:on_received("ack\r\n") end
            assert.are.same(
                { "PON", "STANDBY 0", "AUTO STB 0", "STATUS", "EARLY" },
                h:wires_sent()
            )
        end)

        it("appends a terminator to every wire-bound command", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            assert.are.equal("PON\r\n", h.sent[1].data)
        end)
    end)

    describe("OFFLINE / reconnect backoff", function()
        it("schedules reconnect at 1s on first disconnect", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            h.cs:on_connection_status("OFFLINE")

            assert.are.equal("OFFLINE", h.cs:get_state())
            assert.are.equal(1, h.timer_seq)
            assert.are.equal(1000, h.timers[1].ms)
        end)

        it("walks the canonical backoff schedule and pins at 30s", function()
            local h = make_harness()
            h.cs:start()
            local expected = { 1000, 2000, 5000, 15000, 30000, 30000, 30000 }
            for _, ms in ipairs(expected) do
                h.cs:on_connection_status("OFFLINE")
                assert.are.equal(ms, h.timers[h.timer_seq].ms)
                h:fire_pending_timer()  -- fires the reconnect, calls start()
            end
        end)

        it("resets the backoff index after a successful ONLINE", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("OFFLINE")  -- scheduled at 1000
            h:fire_pending_timer()
            h.cs:on_connection_status("OFFLINE")  -- scheduled at 2000
            h:fire_pending_timer()
            h.cs:on_connection_status("ONLINE")   -- success
            h.cs:on_connection_status("OFFLINE")  -- scheduled at 1000 again
            assert.are.equal(1000, h.timers[h.timer_seq].ms)
        end)

        it("attempts to reconnect when the timer fires", function()
            local h = make_harness()
            h.cs:start()
            local connect_count = 0
            for _, call in ipairs(h.net_calls) do
                if call.op == "connect" then connect_count = connect_count + 1 end
            end
            assert.are.equal(1, connect_count)

            h.cs:on_connection_status("OFFLINE")
            h:fire_pending_timer()

            connect_count = 0
            for _, call in ipairs(h.net_calls) do
                if call.op == "connect" then connect_count = connect_count + 1 end
            end
            assert.are.equal(2, connect_count)
            assert.are.equal("CONNECTING", h.cs:get_state())
        end)

        it("clears in-flight state on disconnect so the next ONLINE re-pumps", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            -- in-flight is "PON"; pretend the link drops mid-flight.
            h.cs:on_connection_status("OFFLINE")
            h:fire_pending_timer()
            h.cs:on_connection_status("ONLINE")

            -- The second ONLINE must immediately put PON back on the wire,
            -- not wait for an ack to a now-dead command.
            assert.are.equal("PON", h:wires_sent()[2])
        end)
    end)

    describe("refresh_matrix_state()", function()
        it("queues a one-shot STATUS poll", function()
            local h = make_harness()
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            for _ = 1, 4 do h.cs:on_received("ack\r\n") end  -- drain init

            h.cs:refresh_matrix_state()
            assert.are.equal("STATUS", h:wires_sent()[5])
        end)

        it("queues even while OFFLINE, dispatching after reconnect", function()
            local h = make_harness()
            h.cs:refresh_matrix_state()  -- before start()

            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            for _ = 1, 4 do h.cs:on_received("ack\r\n") end  -- drain init
            assert.are.equal("STATUS", h:wires_sent()[5])
        end)
    end)

    describe("Debug Mode", function()
        it("suppresses log output when debug_mode is false", function()
            local h = make_harness({ debug_mode = false })
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            assert.are.equal(0, #h.log_messages)
        end)

        it("emits log output when debug_mode is true", function()
            local h = make_harness({ debug_mode = true })
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            assert.is_true(#h.log_messages > 0)
        end)

        it("toggles at runtime via set_debug_mode()", function()
            local h = make_harness({ debug_mode = false })
            h.cs:start()
            h.cs:on_connection_status("ONLINE")
            assert.are.equal(0, #h.log_messages)

            h.cs:set_debug_mode(true)
            h.cs:on_connection_status("OFFLINE")
            assert.is_true(#h.log_messages > 0)
        end)
    end)

    describe("set_host() / set_port()", function()
        it("uses the latest host/port on the next start", function()
            local h = make_harness({ host = "192.168.1.1" })
            h.cs:set_host("192.168.1.99")
            h.cs:set_port(8001)
            h.cs:start()

            assert.are.equal("192.168.1.99", h.net_calls[1].host)
            assert.are.equal(8001, h.net_calls[2].port)
        end)
    end)
end)
