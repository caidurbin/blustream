-- Shared-fixture parity test for the Lua STATUS parser.
--
-- Each .txt fixture under spec/vectors/fixtures/ is parsed and compared to
-- the corresponding .expected.yaml. The Python sibling under
-- tests/test_status_parser.py runs the same comparison; CI fails the build
-- if either runner diverges on any fixture.

package.path = table.concat({
    "control4/dmp168/src/?.lua",
    "control4/dmp168/spec/?.lua",
    package.path,
}, ";")

local status_parser = require("status_parser")
local yaml_lite = require("yaml_lite")

local FIXTURES_DIR = "spec/vectors/fixtures"

local FIXTURES = {
    "status_power_on",
    "status_sleep",
    "status_full_routing",
    "status_partial",
}

local function read_file(path)
    local f, err = io.open(path, "r")
    assert(f, "could not open " .. path .. ": " .. tostring(err))
    local contents = f:read("*a")
    f:close()
    return contents
end

describe("DMP168 STATUS parser (Lua)", function()
    for _, fixture in ipairs(FIXTURES) do
        it("matches expected state for " .. fixture, function()
            local response = read_file(FIXTURES_DIR .. "/" .. fixture .. ".txt")
            local expected = yaml_lite.load(
                read_file(FIXTURES_DIR .. "/" .. fixture .. ".expected.yaml")
            )

            local actual = status_parser.parse(response)

            assert.are.same(expected, actual)
        end)
    end

    it("treats `from_input: null` as the absent-routing sentinel", function()
        -- Synthetic response with one routed and one unrouted output.
        local response = table.concat({
            "Power         Baud    Level Unit    Auto Standby Time(mins)    DSP(%)    Fade    Temp(C)   Uptime",
            "On            57600   %             0                          10        Off     25.0C     0000:01:00:00",
            "",
            "Matrix Config Status",
            "Output        FromIn",
            "Out1 L        In3 L",
            "Out1 R",
            "",
        }, "\n")

        local actual = status_parser.parse(response)

        assert.are.equal(2, #actual.routing)
        assert.are.equal(3, actual.routing[1].from_input)
        assert.is_nil(actual.routing[2].from_input)
    end)
end)
