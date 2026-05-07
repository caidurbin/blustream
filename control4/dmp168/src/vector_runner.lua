-- Lua VectorRunner — execute shared formatter vectors against generated code.
--
-- Mirrors the Python runner at spec/runner.py. Both runners take the same
-- shared vectors file (spec/vectors/formatters.yaml) and assert byte-identical
-- wire output. Drift between the two implementations becomes a CI failure
-- rather than a runtime surprise.
--
-- Public interface (mirrored on the Python side): run_vectors(yaml_path).
--
-- Vector shapes
-- -------------
--
-- Happy path (asserts wire output):
--   - name: power_on emits literal PON
--     op: power_on
--     args: {}
--     expected_wire: "PON"
--
-- Range violation (asserts the formatter raises):
--   - name: output_volume rejects output=10
--     op: output_volume
--     args: {output: 10, level: 50}
--     expected_error: true
--     -- optional: error_contains: "Output must be between 0-8"

local lyaml = require("lyaml")
local generated = require("generated")

local M = {}

local function format_args(args)
    if args == nil then
        return "{}"
    end
    local parts = {}
    for k, v in pairs(args) do
        table.insert(parts, tostring(k) .. "=" .. tostring(v))
    end
    return "{" .. table.concat(parts, ",") .. "}"
end

local function run_one(vector)
    local op = vector.op
    local fn_name = "format_" .. op
    local fn = generated[fn_name]
    if fn == nil then
        error(
            "Generated module has no formatter '" .. fn_name
                .. "' for op '" .. tostring(op) .. "'"
        )
    end

    local args = vector.args or {}

    if vector.expected_error then
        local ok, err = pcall(fn, args)
        if ok then
            error(string.format(
                "vector %q: format_%s(%s) -> %q, expected an error",
                tostring(vector.name or op),
                op,
                format_args(vector.args),
                tostring(err)  -- err here is the return value
            ))
        end
        local substring = vector.error_contains
        if substring ~= nil and not string.find(tostring(err), substring, 1, true) then
            error(string.format(
                "vector %q: format_%s(%s) raised %q, expected message to contain %q",
                tostring(vector.name or op),
                op,
                format_args(vector.args),
                tostring(err),
                tostring(substring)
            ))
        end
        return
    end

    local actual = fn(args)
    local expected = vector.expected_wire
    if actual ~= expected then
        error(string.format(
            "vector %q: format_%s(%s) -> %q, expected %q",
            tostring(vector.name or op),
            op,
            format_args(vector.args),
            tostring(actual),
            tostring(expected)
        ))
    end
end

-- Read every vector in `yaml_path`, format it through the generated module,
-- and assert wire-equality. Returns the number of vectors run; raises on
-- the first mismatch so CI fails loudly.
function M.run_vectors(yaml_path)
    local fh, err = io.open(yaml_path, "r")
    if fh == nil then
        error("could not open " .. yaml_path .. ": " .. tostring(err))
    end
    local content = fh:read("*a")
    fh:close()
    local doc = lyaml.load(content)
    local vectors = (doc and doc.vectors) or {}
    for _, vector in ipairs(vectors) do
        run_one(vector)
    end
    return #vectors
end

return M
