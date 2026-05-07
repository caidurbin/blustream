-- Project-wide luacheck configuration.
--
-- Pinned to Lua 5.1 because Control4 drivers run on the Composer Lua 5.1
-- sandbox; later slices generate driver code under control4/dmp168/src/.

std = "lua51"

exclude_files = {
    ".luarocks",
    "**/build",
    "lua_modules",
}

-- Control4 driver runtime injects globals when Composer loads the driver:
--   * C4         — the Composer API namespace.
--   * Properties — table of driver Property values from driver.xml.
-- Tag both as read-only globals only for files that ship inside the .c4z.
-- Driver lifecycle / callback entry points (OnDriverInit, ExecuteCommand,
-- etc.) are by-convention globals named verbatim by Composer; allow them
-- to be set.
files["control4/**/src/**.lua"] = {
    read_globals = { "C4", "Properties" },
    globals = {
        "OnDriverInit",
        "OnDriverLateInit",
        "OnDriverDestroyed",
        "OnPropertyChanged",
        "OnConnectionStatusChanged",
        "ReceivedFromNetwork",
        "ReceivedFromProxy",
        "ExecuteCommand",
    },
}

-- Busted-style spec files use describe/it/before_each/after_each as globals.
files["control4/**/spec/**_spec.lua"] = {
    std = "+busted",
}
