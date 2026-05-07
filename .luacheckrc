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

-- Control4 driver runtime injects the global `C4` namespace when Composer
-- loads the driver. Tag it as a read-only global only for files that ship
-- inside the .c4z artifact.
files["control4/**/src/**.lua"] = {
    read_globals = { "C4" },
}

-- Busted-style spec files use describe/it/before_each/after_each as globals.
files["control4/**/spec/**_spec.lua"] = {
    std = "+busted",
}
