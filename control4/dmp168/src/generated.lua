-- Generated wire-protocol formatters for the dmp168.
--
-- DO NOT EDIT. Regenerate with: python -m spec.codegen.emit_lua
-- Source: spec/protocol.yaml
-- Spec hash: 620b0eefa790c78d
-- Device: Blustream dmp168
-- Firmware baseline: 1.5.0

local M = {}

M.DEFAULT_PORT = 8000
M.ALTERNATIVE_PORT = 23
M.TERMINATOR = "\r\n"


-- Power the device on.
function M.format_power_on()
    return "PON"
end


return M
