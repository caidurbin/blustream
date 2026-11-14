-- Tests for the driver shell's ReceivedFromNetwork accumulation path.
--
-- driver.lua keeps the unparsed network bytes in a file-local status_buffer
-- and re-parses the whole buffer on every chunk. These specs load the real
-- driver.lua against stub collaborators and watch what it hands to
-- status_parser.parse, which is the buffer's content at each callback. That
-- observes the buffer without widening the driver's surface, and relies on
-- the driver calling parse once per received chunk.

package.path = "control4/dmp168/src/?.lua;" .. package.path

local real_status_parser = require("status_parser")

local DRIVER_PATH = "control4/dmp168/src/driver.lua"
local FIXTURE_PATH = "spec/vectors/fixtures/status_full_routing.txt"
local FIXTURE_ROUTE_COUNT = 16
-- Sanitised capture from a live device: 11,698 bytes, close to the largest
-- single response seen.
local LIVE_FIXTURE_PATH = "tests/fixtures/status_live_full.txt"

-- Mirrors STATUS_BUFFER_MAX_BYTES in driver.lua.
local BUFFER_CAP = 65536
local GARBAGE_CHUNK_BYTES = 4096
local STATUS_CHUNK_BYTES = 40

local NETWORK_BINDING = 6001

local STUBBED_MODULES = {
    "connection",
    "proxy_handler",
    "optimistic_tracker",
    "polling_coordinator",
    "status_parser",
}

local DRIVER_GLOBALS = {
    "OnDriverInit",
    "OnDriverLateInit",
    "OnDriverDestroyed",
    "OnPropertyChanged",
    "OnConnectionStatusChanged",
    "ReceivedFromNetwork",
    "ReceivedFromProxy",
    "ExecuteCommand",
}

local function read_file(path)
    local f, err = io.open(path, "r")
    assert(f, "could not open " .. path .. ": " .. tostring(err))
    local contents = f:read("*a")
    f:close()
    return contents
end

-- Loads a fresh copy of driver.lua (and so a fresh status_buffer) wired to
-- stub collaborators. Returns a harness holding what the stubs recorded.
local function load_driver()
    local h = {
        parsed_lengths = {},
        status_calls = {},
        received = {},
    }

    package.loaded["connection"] = {
        new = function()
            return {
                on_received = function(_, data) table.insert(h.received, data) end,
                set_host = function() end,
                set_port = function() end,
                set_debug_mode = function() end,
                start = function() end,
                stop = function() end,
            }
        end,
    }
    package.loaded["proxy_handler"] = {
        OUTPUT_BINDING_BASE = 2001,
        INPUT_BINDING_BASE = 1001,
        new = function() return {} end,
    }
    package.loaded["optimistic_tracker"] = {
        new = function() return {} end,
    }
    package.loaded["polling_coordinator"] = {
        new = function()
            return {
                on_status = function(_, parsed) table.insert(h.status_calls, parsed) end,
                set_interval_ms = function() end,
                set_debug_mode = function() end,
                start = function() end,
                stop = function() end,
            }
        end,
    }
    package.loaded["status_parser"] = {
        parse = function(text)
            table.insert(h.parsed_lengths, #text)
            return real_status_parser.parse(text)
        end,
    }

    local chunk = assert(loadfile(DRIVER_PATH))
    chunk()
    _G.OnDriverInit(0)

    h.receive = function(data)
        _G.ReceivedFromNetwork(NETWORK_BINDING, 8000, data)
    end
    -- Delivers a STATUS response in small chunks up to its routing section,
    -- then the routing section and the rest in one last chunk. The routing
    -- section is the first to yield rows, so every callback before the last
    -- carries a partial response and only the last completes it.
    h.receive_status_chunked = function(response)
        local routing_at = assert(response:find("Matrix Config Status", 1, true))
        local head = response:sub(1, routing_at - 1)
        for pos = 1, #head, STATUS_CHUNK_BYTES do
            h.receive(head:sub(pos, pos + STATUS_CHUNK_BYTES - 1))
        end
        h.receive(response:sub(routing_at))
    end
    h.max_parsed_length = function()
        local max = 0
        for _, n in ipairs(h.parsed_lengths) do
            if n > max then max = n end
        end
        return max
    end
    return h
end

describe("driver ReceivedFromNetwork status_buffer", function()
    local saved_modules
    local saved_globals

    before_each(function()
        saved_modules = {}
        for _, name in ipairs(STUBBED_MODULES) do
            saved_modules[name] = package.loaded[name]
        end
        saved_globals = {}
        for _, name in ipairs(DRIVER_GLOBALS) do
            saved_globals[name] = _G[name]
        end
    end)

    after_each(function()
        for _, name in ipairs(STUBBED_MODULES) do
            package.loaded[name] = saved_modules[name]
        end
        for _, name in ipairs(DRIVER_GLOBALS) do
            _G[name] = saved_globals[name]
        end
    end)

    it("stays bounded when garbage streams in and never completes a response", function()
        local h = load_driver()
        local garbage = string.rep("x", GARBAGE_CHUNK_BYTES)

        -- 5x the cap in total, delivered in many callbacks.
        for _ = 1, (BUFFER_CAP * 5) / #garbage do
            h.receive(garbage)
        end

        assert.is_true(h.max_parsed_length() <= BUFFER_CAP)
        assert.are.equal(BUFFER_CAP, h.parsed_lengths[#h.parsed_lengths])
        assert.are.equal(0, #h.status_calls)
    end)

    it("stays bounded when a single chunk is larger than the cap", function()
        local h = load_driver()

        h.receive(string.rep("y", BUFFER_CAP * 3))

        assert.are.equal(1, #h.parsed_lengths)
        assert.are.equal(BUFFER_CAP, h.parsed_lengths[1])
    end)

    it("keeps the most recent bytes when it sheds", function()
        local h = load_driver()
        local seen
        package.loaded["status_parser"].parse = function(text)
            seen = text
            error("not a STATUS response")
        end

        h.receive(string.rep("a", BUFFER_CAP))
        h.receive("TAIL")

        assert.are.equal(BUFFER_CAP, #seen)
        assert.are.equal("TAIL", seen:sub(-4))
        assert.are.equal(string.rep("a", BUFFER_CAP - 4), seen:sub(1, -5))
    end)

    it("parses a STATUS response delivered across many callbacks and clears the buffer", function()
        local h = load_driver()
        local response = read_file(FIXTURE_PATH)

        h.receive_status_chunked(response)

        assert.are.equal(1, #h.status_calls)
        assert.are.equal(FIXTURE_ROUTE_COUNT, #h.status_calls[1].routing)
        assert.are.equal(#response, h.parsed_lengths[#h.parsed_lengths])

        -- The buffer was cleared: the next callback parses only its own bytes.
        h.receive("next")
        assert.are.equal(4, h.parsed_lengths[#h.parsed_lengths])
    end)

    it("still parses a chunked STATUS response that arrives after garbage", function()
        local h = load_driver()
        local response = read_file(FIXTURE_PATH)

        -- Enough junk to overflow the cap twice over before the response starts.
        local garbage = string.rep("z", GARBAGE_CHUNK_BYTES)
        for _ = 1, (BUFFER_CAP * 2) / #garbage do
            h.receive(garbage)
        end
        assert.are.equal(0, #h.status_calls)

        h.receive_status_chunked(response)

        assert.is_true(h.max_parsed_length() <= BUFFER_CAP)
        assert.are.equal(1, #h.status_calls)
        assert.are.equal(FIXTURE_ROUTE_COUNT, #h.status_calls[1].routing)

        h.receive("next")
        assert.are.equal(4, h.parsed_lengths[#h.parsed_lengths])
    end)

    it("keeps a live-sized STATUS response whole when it arrives after garbage", function()
        local h = load_driver()
        local response = read_file(LIVE_FIXTURE_PATH)

        local garbage = string.rep("z", GARBAGE_CHUNK_BYTES)
        for _ = 1, (BUFFER_CAP * 2) / #garbage do
            h.receive(garbage)
        end
        h.receive_status_chunked(response)

        assert.are.equal(1, #h.status_calls)
        assert.is_true(#h.status_calls[1].routing > 0)
        -- The parse that completed the response saw all of it, not a tail.
        local completing = h.parsed_lengths[#h.parsed_lengths]
        assert.is_true(completing >= #response)
        assert.is_true(completing <= BUFFER_CAP)
    end)

    it("forwards every chunk to the connection state machine unchanged", function()
        local h = load_driver()

        h.receive("one")
        h.receive(string.rep("q", BUFFER_CAP + 10))

        assert.are.equal(2, #h.received)
        assert.are.equal("one", h.received[1])
        assert.are.equal(BUFFER_CAP + 10, #h.received[2])
    end)
end)
