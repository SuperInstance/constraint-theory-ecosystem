-- FLUX Constraint Engine — Lua 5.3+
-- Pure INT8 saturated constraint checking. Zero dependencies.

local FluxConstraint = {}
FluxConstraint.__index = FluxConstraint

FluxConstraint.INT8_MIN = -127
FluxConstraint.INT8_MAX = 127

function FluxConstraint.saturate(val)
    return math.max(-127, math.min(127, val))
end

function FluxConstraint.new(constraints)
    assert(type(constraints) == "table" and #constraints > 0, "Non-empty constraints required")
    assert(#constraints <= 8, "Max 8 constraints")
    local self = setmetatable({}, FluxConstraint)
    self.constraints = {}
    for i, c in ipairs(constraints) do
        self.constraints[i] = {
            lo = FluxConstraint.saturate(c.lo or c[1]),
            hi = FluxConstraint.saturate(c.hi or c[2]),
            name = c.name or ("C" .. i)
        }
    end
    return self
end

function FluxConstraint:check(value)
    local val = FluxConstraint.saturate(value)
    local errorMask, violatedLo, violatedHi, violatedCount = 0, 0, 0, 0
    local details = {}

    for i, c in ipairs(self.constraints) do
        local loFail = val < c.lo
        local hiFail = val > c.hi
        local passed = not loFail and not hiFail

        if not passed then
            errorMask = errorMask | (1 << (i - 1))
            violatedCount = violatedCount + 1
        end
        if loFail then violatedLo = violatedLo | (1 << (i - 1)) end
        if hiFail then violatedHi = violatedHi | (1 << (i - 1)) end

        details[i] = { name = c.name, lo = c.lo, hi = c.hi, passed = passed }
    end

    local nc = #self.constraints
    local severity = 0
    if violatedCount > 0 then
        if violatedCount <= nc // 4 then severity = 1
        elseif violatedCount <= nc // 2 then severity = 2
        else severity = 3 end
    end

    return {
        errorMask = errorMask,
        severity = severity,
        violatedLo = violatedLo,
        violatedHi = violatedHi,
        violatedCount = violatedCount,
        passed = violatedCount == 0,
        details = details
    }
end

function FluxConstraint:checkBatch(values)
    local results, stats = {}, { pass = 0, caution = 0, warning = 0, critical = 0 }
    local labels = { [0] = "pass", [1] = "caution", [2] = "warning", [3] = "critical" }
    for i, v in ipairs(values) do
        local r = self:check(v)
        results[i] = r
        stats[labels[r.severity]] = stats[labels[r.severity]] + 1
    end
    return results, stats
end

function FluxConstraint:benchmark(iterations)
    iterations = iterations or 1000000
    local t0 = os.clock()
    for i = 1, iterations do
        self:check((i % 254) - 127)
    end
    local elapsed = os.clock() - t0
    local rate = iterations * #self.constraints / elapsed
    return rate, elapsed * 1000
end

-- Presets
FluxConstraint.presets = {
    aviation = {
        { lo = -55, hi = 70, name = "cabin_temp_C" },
        { lo = 75, hi = 101, name = "cabin_pressure_kPa" },
        { lo = 0, hi = 100, name = "fuel_flow_pct" },
        { lo = 60, hi = 100, name = "hydraulic_pct" },
    },
    medical = {
        { lo = 36, hi = 38, name = "body_temp_C" },
        { lo = 60, hi = 100, name = "heart_rate_bpm" },
        { lo = 95, hi = 100, name = "spo2_pct" },
        { lo = 80, hi = 120, name = "bp_systolic_mmHg" },
    },
    maritime = {
        { lo = -2, hi = 35, name = "sea_temp_C" },
        { lo = 50, hi = 100, name = "hull_integrity_pct" },
        { lo = 0, hi = 50, name = "wave_height_m" },
        { lo = 0, hi = 80, name = "wind_speed_kn" },
    },
    automotive = {
        { lo = -40, hi = 60, name = "battery_temp_C" },
        { lo = 0, hi = 100, name = "soc_pct" },
        { lo = 0, hi = 100, name = "charge_rate_pct" },
        { lo = 20, hi = 80, name = "cabin_temp_C" },
    },
    energy = {
        { lo = 49, hi = 51, name = "grid_freq_Hz_x10" },
        { lo = 95, hi = 105, name = "voltage_pct" },
        { lo = 0, hi = 80, name = "transformer_temp_C" },
        { lo = 0, hi = 100, name = "line_load_pct" },
    },
}

function FluxConstraint.fromPreset(name)
    local cs = FluxConstraint.presets[name]
    if not cs then error("Unknown preset: " .. name) end
    return FluxConstraint.new(cs)
end

-- Self-test
if arg and arg[0] and arg[0]:match("flux_constraint") then
    print("FLUX Constraint Engine - Lua")
    print("============================")

    assert(FluxConstraint.saturate(-128) == -127, "sat(-128)")
    assert(FluxConstraint.saturate(128) == 127, "sat(128)")
    print("  saturate: OK")

    local fc = FluxConstraint.new({ { lo = 0, hi = 100, name = "test" } })
    assert(fc:check(50).passed, "pass")
    assert(not fc:check(150).passed, "fail")
    print("  check: OK")

    local fc2 = FluxConstraint.new({
        { lo = 0, hi = 10, name = "a" }, { lo = 0, hi = 10, name = "b" },
        { lo = 0, hi = 10, name = "c" }, { lo = 0, hi = 10, name = "d" }
    })
    assert(fc2:check(50).severity == 3, "critical")
    print("  severity: OK")

    local fc3 = FluxConstraint.fromPreset("aviation")
    assert(#fc3.constraints == 4, "preset")
    print("  presets: OK")

    local rate, ms = fc3:benchmark()
    print(string.format("  Benchmark: %.1fM checks/sec (%.1fms)", rate / 1e6, ms))

    print("  All tests pass")
end

return FluxConstraint
