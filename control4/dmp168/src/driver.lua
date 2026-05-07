-- Blustream DMP168 Control4 driver — minimal shell.
--
-- This file is the no-op driver shell described in issue #17. The driver
-- registers with Composer Pro (the proxy and bindings are declared in
-- driver.xml) but exposes no functional behavior yet. Connection
-- handling, polling, the optimistic state tracker, and the
-- SELECT_AUDIO_DEVICE proxy command handler are added in later slices —
-- see docs/control4-driver-plan.md, phase 2.
--
-- C4:AllowExecute(true) is injected by drivers-driverpackager when the
-- archive is built with -ae (the dev flavor); release builds omit it.
-- See tools/build_c4z.py.

function OnDriverInit(driverInitType)  -- luacheck: no unused args
end

function OnDriverLateInit(driverInitType)  -- luacheck: no unused args
end

function OnDriverDestroyed()
end

function ExecuteCommand(strCommand, tParams)  -- luacheck: no unused args
end

function ReceivedFromProxy(idBinding, strCommand, tParams)  -- luacheck: no unused args
end
