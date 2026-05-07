-- Tests for the Lua VectorRunner (control4/dmp168/src/vector_runner.lua).
--
-- A failure here flags drift between the spec, the generated Lua primitives,
-- and the shared vector contract. Mirrors tests/test_vector_runner.py.

-- Allow `require("vector_runner")` and `require("generated")` from this spec
-- when busted is invoked from the repo root.
package.path = "control4/dmp168/src/?.lua;" .. package.path

local runner = require("vector_runner")

describe("Lua VectorRunner", function()
    it("passes the committed formatter vectors", function()
        local count = runner.run_vectors("spec/vectors/formatters.yaml")
        assert.is_true(count >= 1)
    end)

    it("raises on wire mismatch", function()
        local tmp = os.tmpname()
        local fh = assert(io.open(tmp, "w"))
        fh:write(
            "vectors:\n"
                .. "  - name: wrong expectation\n"
                .. "    op: power_on\n"
                .. "    args: {}\n"
                .. "    expected_wire: NOPE\n"
        )
        fh:close()

        local ok, err = pcall(runner.run_vectors, tmp)
        os.remove(tmp)
        assert.is_false(ok)
        assert.is_truthy(string.find(tostring(err), "PON", 1, true))
        assert.is_truthy(string.find(tostring(err), "NOPE", 1, true))
    end)

    it("raises when an op has no matching generated formatter", function()
        local tmp = os.tmpname()
        local fh = assert(io.open(tmp, "w"))
        fh:write(
            "vectors:\n"
                .. "  - name: missing op\n"
                .. "    op: not_a_real_op\n"
                .. "    args: {}\n"
                .. "    expected_wire: x\n"
        )
        fh:close()

        local ok, err = pcall(runner.run_vectors, tmp)
        os.remove(tmp)
        assert.is_false(ok)
        assert.is_truthy(string.find(tostring(err), "not_a_real_op", 1, true))
    end)

    it("returns 0 for a vectors-empty file", function()
        local tmp = os.tmpname()
        local fh = assert(io.open(tmp, "w"))
        fh:write("vectors: []\n")
        fh:close()

        local count = runner.run_vectors(tmp)
        os.remove(tmp)
        assert.are.equal(0, count)
    end)
end)
