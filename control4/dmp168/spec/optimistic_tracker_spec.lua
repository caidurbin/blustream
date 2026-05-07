-- Tests for the Lua OptimisticStateTracker.
--
-- The tracker is the pure-logic core of the optimistic-update + lockout
-- contract from ADR-0004. Given (current state, command history, current
-- time), it decides which outputs adopt a polled value (ground truth for
-- the matrix) and which stay pinned to the most recent commanded value
-- because the lockout window has not yet expired. Tests inject the clock
-- explicitly so time-boundary cases are deterministic. See issue #22.

package.path = "control4/dmp168/src/?.lua;" .. package.path

local optimistic_tracker = require("optimistic_tracker")

local function new_tracker(opts)
    return optimistic_tracker.new(opts)
end

describe("OptimisticStateTracker", function()
    describe("construction", function()
        it("defaults the lockout window to 2000 ms (ADR-0004)", function()
            assert.are.equal(2000, optimistic_tracker.DEFAULT_LOCKOUT_MS)
            local t = new_tracker()
            -- The lockout default is observable through is_locked() at the
            -- boundary: 1999 ms inside the window is locked, 2000 ms out.
            t:note_command(1, 5, 0)
            assert.is_true(t:is_locked(1, 1999))
            assert.is_false(t:is_locked(1, 2000))
        end)

        it("starts with an empty routing snapshot", function()
            local t = new_tracker()
            assert.are.same({}, t:get_routing())
        end)

        it("accepts a custom lockout_ms for tests that need a tighter window", function()
            local t = new_tracker({ lockout_ms = 500 })
            t:note_command(1, 5, 0)
            assert.is_true(t:is_locked(1, 499))
            assert.is_false(t:is_locked(1, 500))
        end)
    end)

    describe("note_command()", function()
        it("records the commanded routing immediately", function()
            local t = new_tracker()
            t:note_command(2, 7, 1000)
            assert.are.equal(7, t:get_routing()[2])
        end)

        it("treats nil input as an unroute (no source)", function()
            local t = new_tracker()
            t:note_command(2, 5, 0)
            t:note_command(2, nil, 100)
            assert.is_nil(t:get_routing()[2])
        end)

        it("opens a fresh lockout window per output independently", function()
            local t = new_tracker()
            t:note_command(1, 3, 0)
            t:note_command(2, 4, 1500)
            -- Output 1's window has expired by t=2000; output 2's hasn't.
            assert.is_false(t:is_locked(1, 2000))
            assert.is_true(t:is_locked(2, 2000))
        end)
    end)

    describe("reconcile() — single command + poll inside lockout", function()
        it("ignores polled state for an output whose lockout has not expired", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)            -- commanded: out 1 <- in 5
            local changes = t:reconcile({ [1] = 9 }, 1000)  -- 1s later, < 2s
            assert.are.same({}, changes)
            assert.are.equal(5, t:get_routing()[1])
        end)

        it("does not undo the optimistic update when the device echoes stale state", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)
            -- Stale STATUS with the old input is what races the issue's
            -- "stale poll undoes the optimistic update" failure mode.
            local changes = t:reconcile({ [1] = 2 }, 1999)
            assert.are.same({}, changes)
            assert.are.equal(5, t:get_routing()[1])
        end)
    end)

    describe("reconcile() — single command + poll outside lockout", function()
        it("accepts polled state once the lockout has expired", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)
            local changes = t:reconcile({ [1] = 9 }, 2500)
            assert.are.same(
                { { output = 1, prev_input = 5, new_input = 9 } },
                changes
            )
            assert.are.equal(9, t:get_routing()[1])
        end)

        it("treats polled state as ground truth for outputs never commanded", function()
            -- Out-of-band web-GUI change appears in a poll for an output
            -- the driver hasn't touched. The diff fires immediately.
            local t = new_tracker()
            local changes = t:reconcile({ [3] = 8 }, 1000)
            assert.are.same(
                { { output = 3, prev_input = nil, new_input = 8 } },
                changes
            )
            assert.are.equal(8, t:get_routing()[3])
        end)
    end)

    describe("reconcile() — double command within window", function()
        it("preserves the most recent commanded state across both commands", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)
            t:note_command(1, 7, 500)  -- second command inside the window
            assert.are.equal(7, t:get_routing()[1])

            -- A poll at t=1500 echoing the OLD command's input must not win.
            local changes = t:reconcile({ [1] = 5 }, 1500)
            assert.are.same({}, changes)
            assert.are.equal(7, t:get_routing()[1])
        end)

        it("re-arms the lockout from the most recent command, not the first", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)
            t:note_command(1, 7, 1500)
            -- Lockout from t=1500 expires at t=3500. A poll at t=2500 (3s
            -- past the FIRST command) is still inside the SECOND's window.
            assert.is_true(t:is_locked(1, 2500))
            local changes = t:reconcile({ [1] = 9 }, 2500)
            assert.are.same({}, changes)
            assert.are.equal(7, t:get_routing()[1])
        end)
    end)

    describe("reconcile() — disagreement vs. confirmation", function()
        it("ignores polls that disagree with the commanded state inside the window", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)
            local changes = t:reconcile({ [1] = 2 }, 1000)
            assert.are.same({}, changes)
            assert.are.equal(5, t:get_routing()[1])
        end)

        it("emits no change when the poll confirms the commanded state", function()
            -- Inside the lockout: even a confirming poll is a no-op (no diff).
            local t = new_tracker()
            t:note_command(1, 5, 0)
            local changes = t:reconcile({ [1] = 5 }, 1000)
            assert.are.same({}, changes)
            assert.are.equal(5, t:get_routing()[1])
        end)

        it("emits no change when an outside-window poll confirms the commanded state", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)
            local changes = t:reconcile({ [1] = 5 }, 5000)
            assert.are.same({}, changes)
            assert.are.equal(5, t:get_routing()[1])
        end)
    end)

    describe("reconcile() — exact 2-second boundary", function()
        it("treats t=lockout_ms as outside the window (poll wins)", function()
            -- Defines the boundary semantics: lockout is (now - cmd) <
            -- lockout_ms, so exactly at the boundary we accept the poll.
            local t = new_tracker()
            t:note_command(1, 5, 0)
            assert.is_false(t:is_locked(1, 2000))
            local changes = t:reconcile({ [1] = 9 }, 2000)
            assert.are.same(
                { { output = 1, prev_input = 5, new_input = 9 } },
                changes
            )
            assert.are.equal(9, t:get_routing()[1])
        end)

        it("treats t=lockout_ms-1 as inside the window (commanded wins)", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)
            assert.is_true(t:is_locked(1, 1999))
            local changes = t:reconcile({ [1] = 9 }, 1999)
            assert.are.same({}, changes)
            assert.are.equal(5, t:get_routing()[1])
        end)
    end)

    describe("reconcile() — multi-output diff", function()
        it("returns one entry per changed output and applies them all", function()
            local t = new_tracker()
            -- Seed two outputs from a prior poll so the diff has prev values.
            t:reconcile({ [1] = 1, [2] = 2, [3] = 3 }, 0)
            local changes = t:reconcile({ [1] = 4, [2] = 2, [3] = 7 }, 1000)
            -- Output 2 unchanged; outputs 1 and 3 changed.
            table.sort(changes, function(a, b) return a.output < b.output end)
            assert.are.same(
                {
                    { output = 1, prev_input = 1, new_input = 4 },
                    { output = 3, prev_input = 3, new_input = 7 },
                },
                changes
            )
            assert.are.equal(4, t:get_routing()[1])
            assert.are.equal(2, t:get_routing()[2])
            assert.are.equal(7, t:get_routing()[3])
        end)

        it("locks individual outputs without affecting their peers", function()
            local t = new_tracker()
            t:reconcile({ [1] = 1, [2] = 2 }, 0)
            t:note_command(1, 5, 100)  -- output 1 enters lockout
            -- Same poll at t=500 (output 1 locked, output 2 not).
            local changes = t:reconcile({ [1] = 1, [2] = 9 }, 500)
            assert.are.same(
                { { output = 2, prev_input = 2, new_input = 9 } },
                changes
            )
            assert.are.equal(5, t:get_routing()[1])
            assert.are.equal(9, t:get_routing()[2])
        end)

        it("treats a polled nil-from-existing-input as an unroute diff", function()
            local t = new_tracker()
            t:reconcile({ [1] = 5 }, 0)
            local changes = t:reconcile({ [1] = nil }, 5000)
            assert.are.same(
                { { output = 1, prev_input = 5, new_input = nil } },
                changes
            )
            assert.is_nil(t:get_routing()[1])
        end)
    end)

    describe("get_routing()", function()
        it("returns a snapshot, not the live table", function()
            local t = new_tracker()
            t:note_command(1, 5, 0)
            local snap = t:get_routing()
            snap[1] = 99
            assert.are.equal(5, t:get_routing()[1])
        end)
    end)
end)
