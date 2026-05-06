# FLUX Constraint Engine — Julia
# Pure INT8 saturated constraint checking. Zero dependencies.

const INT8_MIN = Int8(-127)
const INT8_MAX = Int8(127)

saturate(val::Integer) = clamp(val, -127, 127)

@enum Severity begin
    PASS = 0
    CAUTION = 1
    WARNING = 2
    CRITICAL = 3
end

struct Constraint
    lo::Int
    hi::Int
    name::String
    Constraint(lo, hi, name="") = new(lo, hi, name)
end

struct FluxResult
    error_mask::Int
    severity::Severity
    violated_lo::Int
    violated_hi::Int
    violated_count::Int
    passed::Bool
end

struct FluxChecker
    constraints::Vector{Constraint}
    function FluxChecker(cs::Vector{Constraint})
        @assert !isempty(cs) "Non-empty constraints required"
        @assert length(cs) <= 8 "Max 8 constraints"
        new(cs)
    end
    FluxChecker(cs::Vector) = FluxChecker([Constraint(c...) for c in cs])
end

function check(fc::FluxChecker, value::Integer)
    val = saturate(value)
    error_mask = 0
    violated_lo = 0
    violated_hi = 0
    violated_count = 0

    for (i, c) in enumerate(fc.constraints)
        lo = saturate(c.lo)
        hi = saturate(c.hi)
        lo_fail = val < lo
        hi_fail = val > hi
        if lo_fail || hi_fail
            error_mask |= (1 << (i-1))
            violated_count += 1
        end
        if lo_fail violated_lo |= (1 << (i-1)) end
        if hi_fail violated_hi |= (1 << (i-1)) end
    end

    nc = length(fc.constraints)
    sev = if violated_count == 0 PASS
          elseif violated_count <= nc ÷ 4 CAUTION
          elseif violated_count <= nc ÷ 2 WARNING
          else CRITICAL end

    FluxResult(error_mask, sev, violated_lo, violated_hi, violated_count, sev == PASS)
end

function check_batch(fc::FluxChecker, values::Vector{<:Integer})
    results = [check(fc, v) for v in values]
    stats = Dict(
        :pass => count(r -> r.severity == PASS, results),
        :caution => count(r -> r.severity == CAUTION, results),
        :warning => count(r -> r.severity == WARNING, results),
        :critical => count(r -> r.severity == CRITICAL, results),
    )
    results, stats
end

function benchmark(fc::FluxChecker, iterations::Int=1_000_000)
    t0 = time_ns()
    for i in 1:iterations
        check(fc, (i % 254) - 127)
    end
    elapsed_ms = (time_ns() - t0) / 1e6
    rate = iterations * length(fc.constraints) / (elapsed_ms / 1000.0)
    rate, elapsed_ms
end

const PRESETS = Dict(
    "aviation" => [Constraint(-55, 70, "cabin_temp_C"), Constraint(75, 101, "cabin_pressure_kPa"),
                   Constraint(0, 100, "fuel_flow_pct"), Constraint(60, 100, "hydraulic_pct")],
    "medical" => [Constraint(36, 38, "body_temp_C"), Constraint(60, 100, "heart_rate_bpm"),
                  Constraint(95, 100, "spo2_pct"), Constraint(80, 120, "bp_systolic_mmHg")],
    "maritime" => [Constraint(-2, 35, "sea_temp_C"), Constraint(50, 100, "hull_integrity_pct"),
                   Constraint(0, 50, "wave_height_m"), Constraint(0, 80, "wind_speed_kn")],
    "automotive" => [Constraint(-40, 60, "battery_temp_C"), Constraint(0, 100, "soc_pct"),
                     Constraint(0, 100, "charge_rate_pct"), Constraint(20, 80, "cabin_temp_C")],
    "energy" => [Constraint(49, 51, "grid_freq_Hz_x10"), Constraint(95, 105, "voltage_pct"),
                 Constraint(0, 80, "transformer_temp_C"), Constraint(0, 100, "line_load_pct")],
)

from_preset(name::String) = FluxChecker(PRESETS[name])

# Self-test
if abspath(PROGRAM_FILE) == @__FILE__
    println("FLUX Constraint Engine — Julia")
    println("==============================")

    @assert saturate(-128) == -127
    @assert saturate(128) == 127
    println("  saturate: OK")

    fc = FluxChecker([Constraint(0, 100)])
    @assert check(fc, 50).passed
    @assert !check(fc, 150).passed
    println("  check: OK")

    fc2 = FluxChecker([Constraint(0,10), Constraint(0,10), Constraint(0,10), Constraint(0,10)])
    r = check(fc2, 50)
    @assert r.severity == CRITICAL && r.violated_count == 4
    println("  severity: OK")

    fc3 = from_preset("aviation")
    @assert length(fc3.constraints) == 4
    println("  presets: OK")

    rate, ms = benchmark(fc3)
    @printf("  Benchmark: %.1fM checks/sec (%.1fms)\n", rate/1e6, ms)
    println("  All tests pass")
end
