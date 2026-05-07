-- Tests for the Lua ProxyHandler.
--
-- The proxy handler is the thin glue between Composer's audio_matrix_switch
-- proxy callbacks and the wire protocol. It translates SELECT_AUDIO_DEVICE
-- commands into OUT/FR (or OUT/REM) wire strings via the codegen-emitted
-- formatters, enqueues them on the ConnectionStateMachine, and applies an
-- optimistic update to its own routing table so subsequent gets reflect the
-- latest commanded state. Lockout logic and poll reconciliation arrive in a
-- later slice.
--
-- The state machine is mocked here so the tests assert on observable
-- behavior (what was enqueued, what state results) rather than on the
-- transport. See issue #21.

package.path = "control4/dmp168/src/?.lua;" .. package.path

local proxy_handler = require("proxy_handler")
local generated = require("generated")

local OUTPUT_BASE = 2001  -- matches driver.xml audio_providers

local function make_harness(opts)
    opts = opts or {}
    local h = {
        sent = {},
        log_messages = {},
    }
    -- Minimal stand-in for ConnectionStateMachine. Records every call to
    -- :send() so tests can inspect FIFO order without driving the full TCP
    -- state machine.
    h.connection = {
        send = function(self, wire)  -- luacheck: no unused args
            table.insert(h.sent, wire)
        end,
    }
    h.log = function(msg) table.insert(h.log_messages, msg) end

    h.ph = proxy_handler.new({
        connection = h.connection,
        log = h.log,
        debug_mode = opts.debug_mode,
    })
    return h
end

describe("ProxyHandler", function()
    describe("construction", function()
        it("requires a connection dependency", function()
            assert.has_error(function() proxy_handler.new({}) end)
            assert.has_error(function() proxy_handler.new(nil) end)
        end)

        it("starts with an empty routing table", function()
            local h = make_harness()
            assert.are.same({}, h.ph:get_routing())
        end)

        it("exposes the canonical binding bases that match driver.xml", function()
            assert.are.equal(2001, proxy_handler.OUTPUT_BINDING_BASE)
            assert.are.equal(8, proxy_handler.OUTPUT_COUNT)
            assert.are.equal(1001, proxy_handler.INPUT_BINDING_BASE)
            assert.are.equal(16, proxy_handler.INPUT_COUNT)
        end)
    end)

    describe("SELECT_AUDIO_DEVICE — routing translation", function()
        it("translates output binding 2001 + BINDID 1003 to OUT 1 FR 3", function()
            local h = make_harness()
            h.ph:on_proxy_command(OUTPUT_BASE, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            assert.are.same({ "OUT 1 FR 3" }, h.sent)
        end)

        it("translates the corner cases of the 8x16 binding grid", function()
            local cases = {
                { out_bind = 2001, in_bind = 1001, wire = "OUT 1 FR 1" },
                { out_bind = 2008, in_bind = 1016, wire = "OUT 8 FR 16" },
                { out_bind = 2003, in_bind = 1015, wire = "OUT 3 FR 15" },
                { out_bind = 2007, in_bind = 1002, wire = "OUT 7 FR 2" },
            }
            for _, c in ipairs(cases) do
                local h = make_harness()
                h.ph:on_proxy_command(c.out_bind, "SELECT_AUDIO_DEVICE",
                    { BINDID = c.in_bind })
                assert.are.same({ c.wire }, h.sent)
            end
        end)

        it("uses the codegen-emitted format_route (no hardcoded wire string)", function()
            -- Sanity check: the wire string we expect must equal what the
            -- generated formatter produces for the same args. Pins the
            -- handler to the spec rather than to a literal in this test.
            assert.are.equal(
                "OUT 4 FR 9",
                generated.format_route({ output = 4, input_ch = 9 })
            )
            local h = make_harness()
            h.ph:on_proxy_command(2004, "SELECT_AUDIO_DEVICE", { BINDID = 1009 })
            assert.are.same({ "OUT 4 FR 9" }, h.sent)
        end)

        it("accepts BINDID as a string (Composer sometimes hands strings)", function()
            local h = make_harness()
            h.ph:on_proxy_command(OUTPUT_BASE, "SELECT_AUDIO_DEVICE",
                { BINDID = "1005" })
            assert.are.same({ "OUT 1 FR 5" }, h.sent)
        end)
    end)

    describe("SELECT_AUDIO_DEVICE — optimistic state update", function()
        it("records the new routing immediately on issue", function()
            local h = make_harness()
            h.ph:on_proxy_command(OUTPUT_BASE, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            -- State updates BEFORE any device acknowledgment lands; this is
            -- the optimistic part of the contract. Per ADR-0004 the lockout
            -- window arrives in a later slice; here we only assert the
            -- update itself.
            assert.are.equal(3, h.ph:get_routing()[1])
        end)

        it("overwrites prior routing when a new input is selected", function()
            local h = make_harness()
            h.ph:on_proxy_command(OUTPUT_BASE, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            h.ph:on_proxy_command(OUTPUT_BASE, "SELECT_AUDIO_DEVICE", { BINDID = 1007 })
            assert.are.equal(7, h.ph:get_routing()[1])
        end)

        it("tracks routing per output independently", function()
            local h = make_harness()
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            h.ph:on_proxy_command(2002, "SELECT_AUDIO_DEVICE", { BINDID = 1009 })
            h.ph:on_proxy_command(2008, "SELECT_AUDIO_DEVICE", { BINDID = 1016 })
            local routing = h.ph:get_routing()
            assert.are.equal(3, routing[1])
            assert.are.equal(9, routing[2])
            assert.are.equal(16, routing[8])
        end)
    end)

    describe("SELECT_AUDIO_DEVICE — unroute (BINDID 0)", function()
        it("emits OUT n REM <prev> when a previously-routed output is cleared", function()
            local h = make_harness()
            h.ph:on_proxy_command(OUTPUT_BASE, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            h.ph:on_proxy_command(OUTPUT_BASE, "SELECT_AUDIO_DEVICE", { BINDID = 0 })
            assert.are.same({ "OUT 1 FR 3", "OUT 1 REM 3" }, h.sent)
            assert.is_nil(h.ph:get_routing()[1])
        end)

        it("is a no-op when clearing an already-unrouted output", function()
            local h = make_harness()
            h.ph:on_proxy_command(OUTPUT_BASE, "SELECT_AUDIO_DEVICE", { BINDID = 0 })
            assert.are.same({}, h.sent)
            assert.is_nil(h.ph:get_routing()[1])
        end)
    end)

    describe("queue behavior under back-to-back commands", function()
        it("enqueues every command in the order it was received", function()
            local h = make_harness()
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1001 })
            h.ph:on_proxy_command(2002, "SELECT_AUDIO_DEVICE", { BINDID = 1002 })
            h.ph:on_proxy_command(2003, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            assert.are.same(
                { "OUT 1 FR 1", "OUT 2 FR 2", "OUT 3 FR 3" },
                h.sent
            )
        end)

        it("enqueues a duplicate (same output, same input) without dedup", function()
            -- The proxy handler doesn't try to be clever about idempotence —
            -- the dealer or programmer might rely on the wire command landing.
            local h = make_harness()
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            assert.are.same({ "OUT 1 FR 3", "OUT 1 FR 3" }, h.sent)
        end)
    end)

    describe("invalid / unknown bindings", function()
        it("ignores SELECT_AUDIO_DEVICE on a non-output binding", function()
            local h = make_harness()
            h.ph:on_proxy_command(1001, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            assert.are.same({}, h.sent)
            assert.are.same({}, h.ph:get_routing())
        end)

        it("ignores SELECT_AUDIO_DEVICE on an out-of-range output binding", function()
            local h = make_harness()
            h.ph:on_proxy_command(2009, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            h.ph:on_proxy_command(9999, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            assert.are.same({}, h.sent)
        end)

        it("ignores SELECT_AUDIO_DEVICE with an out-of-range input binding", function()
            local h = make_harness()
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1017 })
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 999 })
            assert.are.same({}, h.sent)
            assert.is_nil(h.ph:get_routing()[1])
        end)

        it("ignores SELECT_AUDIO_DEVICE with a missing BINDID", function()
            local h = make_harness()
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", {})
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", nil)
            assert.are.same({}, h.sent)
        end)

        it("ignores unknown proxy commands", function()
            local h = make_harness()
            h.ph:on_proxy_command(2001, "SOMETHING_ELSE", { BINDID = 1003 })
            h.ph:on_proxy_command(2001, "SET_AUDIO_VOLUME_LEVEL", { LEVEL = 50 })
            assert.are.same({}, h.sent)
            assert.are.same({}, h.ph:get_routing())
        end)
    end)

    describe("Debug Mode", function()
        it("suppresses log output when debug_mode is false", function()
            local h = make_harness({ debug_mode = false })
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            assert.are.equal(0, #h.log_messages)
        end)

        it("emits log output when debug_mode is true", function()
            local h = make_harness({ debug_mode = true })
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            assert.is_true(#h.log_messages > 0)
        end)

        it("toggles at runtime via set_debug_mode()", function()
            local h = make_harness({ debug_mode = false })
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1003 })
            assert.are.equal(0, #h.log_messages)

            h.ph:set_debug_mode(true)
            h.ph:on_proxy_command(2001, "SELECT_AUDIO_DEVICE", { BINDID = 1004 })
            assert.is_true(#h.log_messages > 0)
        end)
    end)
end)
