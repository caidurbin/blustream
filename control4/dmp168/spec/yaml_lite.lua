-- Tiny YAML loader for the shared expected-state fixtures.
--
-- Handles only the subset we author under spec/vectors/fixtures/*.expected.yaml:
--
--   * a single root block mapping (no document markers)
--   * scalar values: int, float, true / false, null, plain or double-quoted
--     strings
--   * block-sequence values whose items are flow-style mappings, e.g.:
--
--         routing:
--           - {output: 1, channel: "L", from_input: 1}
--
--   * empty inline sequences: `inputs: []`
--
-- Anything outside this subset (block-style nested mappings as sequence items,
-- multi-line strings, anchors / aliases, etc.) is intentionally unsupported.
-- A lyaml dependency in CI would be heavier than the format demands.

local M = {}

local function strip(s)
    return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function leading_spaces(s)
    local _, count = s:find("^( *)")
    return count or 0
end

local function unquote(s)
    if #s >= 2 and s:sub(1, 1) == '"' and s:sub(-1) == '"' then
        return s:sub(2, -2)
    end
    return s
end

local function parse_scalar(s)
    s = strip(s)
    if s == "" or s == "null" or s == "~" then
        return nil, true -- second return is "is_null"
    end
    if s == "true" then return true end
    if s == "false" then return false end
    if s:sub(1, 1) == '"' then
        return unquote(s)
    end
    local n = tonumber(s)
    if n ~= nil then return n end
    return s
end

-- Split a flow-mapping body on top-level commas (no nesting expected here).
local function split_flow_pairs(body)
    local pairs_out = {}
    local depth = 0
    local in_quote = false
    local start = 1
    for i = 1, #body do
        local c = body:sub(i, i)
        if c == '"' then
            in_quote = not in_quote
        elseif not in_quote then
            if c == "{" or c == "[" then
                depth = depth + 1
            elseif c == "}" or c == "]" then
                depth = depth - 1
            elseif c == "," and depth == 0 then
                table.insert(pairs_out, body:sub(start, i - 1))
                start = i + 1
            end
        end
    end
    table.insert(pairs_out, body:sub(start))
    return pairs_out
end

local function parse_flow_mapping(s)
    -- s is the entire string including the wrapping braces.
    local body = strip(s):sub(2, -2)
    body = strip(body)
    local result = {}
    if body == "" then return result end
    for _, pair in ipairs(split_flow_pairs(body)) do
        local key, value = pair:match("^%s*([^:%s]+)%s*:%s*(.*)$")
        if key then
            local scalar, is_null = parse_scalar(value)
            if not is_null then
                result[key] = scalar
            end
            -- A null value omits the key, matching Python's dict behavior
            -- where the parser returns from_input=None and the YAML expected
            -- state is `from_input: null`.
        end
    end
    return result
end

local function parse_value(value_str)
    value_str = strip(value_str)
    if value_str:sub(1, 1) == "{" then
        return parse_flow_mapping(value_str), false
    end
    if value_str == "[]" then
        return {}, false
    end
    return parse_scalar(value_str)
end

function M.load(text)
    local lines = {}
    for line in (text .. "\n"):gmatch("([^\r\n]*)\r?\n") do
        -- Drop blank lines outright; they have no semantic meaning here.
        if strip(line) ~= "" then
            table.insert(lines, line)
        end
    end

    local root = {}
    local i = 1
    while i <= #lines do
        local line = lines[i]
        local indent = leading_spaces(line)
        local content = strip(line)
        if indent == 0 then
            local key, raw_value = content:match("^([^:]+):%s*(.*)$")
            if not key then
                error("yaml_lite: expected key at line " .. i .. ": " .. line)
            end
            key = strip(key)
            if raw_value == "" then
                -- Block-sequence value: collect indented `- ...` items that
                -- follow at indent >= 2.
                local items = {}
                i = i + 1
                while i <= #lines do
                    local next_line = lines[i]
                    local next_indent = leading_spaces(next_line)
                    local next_content = strip(next_line)
                    if next_indent < 2 or next_content:sub(1, 2) ~= "- " then
                        break
                    end
                    local item_value = next_content:sub(3)
                    local parsed = parse_value(item_value)
                    table.insert(items, parsed)
                    i = i + 1
                end
                root[key] = items
            else
                local scalar, is_null = parse_value(raw_value)
                if not is_null then
                    root[key] = scalar
                end
                i = i + 1
            end
        else
            error("yaml_lite: unexpected indented line " .. i .. ": " .. line)
        end
    end
    return root
end

return M
