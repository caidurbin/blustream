-- Smoke test for the Lua test harness.
--
-- Exists so the CI Lua job has at least one passing assertion before any
-- real driver code lands. Later slices (codegen vector runner, status
-- parser, optimistic state tracker) replace and extend this file.

describe("Lua test harness", function()
    it("runs a passing assertion", function()
        assert.are.equal(2, 1 + 1)
    end)

    it("targets Lua 5.1 for Control4 compatibility", function()
        -- _VERSION is "Lua 5.1" on stock Lua 5.1.x and on LuaJIT when the
        -- 5.1 compatibility table is active. Either is acceptable for the
        -- driver runtime; both Composer and our CI image satisfy this.
        assert.are.equal("Lua 5.1", _VERSION)
    end)
end)
