// FLUX Constraint Engine — Futhark (2017, GPU-Native Functional)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: Futhark compiles pure functional array code DIRECTLY to GPU.
// Batch constraint checking is a MAP operation over the value array.
// No CUDA, no OpenCL, no GPU programming — just pure functions.
// The compiler handles parallelism. You write math, it writes kernels.
//
// "Write pure functions. The compiler makes them run on GPU.
//  No kernel launches. No memory management. No synchronization.
//  Constraint checking as a parallel map — because it IS one."

module flux_constraint

// ══════════════════════════════════════════════════════════════════
//  Constants
// ══════════════════════════════════════════════════════════════════

def INT8_MIN : i32 = -127
def INT8_MAX : i32 = 127
def MAX_CONSTRAINTS : i32 = 8

// ══════════════════════════════════════════════════════════════════
//  Types
// ══════════════════════════════════════════════════════════════════

type severity = #pass | #caution | #warning | #critical

type constraint = {
    lo: i32,
    hi: i32,
    name: string  // Futhark doesn't have great string support, but we keep it for docs
}

type flux_result = {
    error_mask: i32,
    severity: i32,        // 0=PASS, 1=CAUTION, 2=WARNING, 3=CRITICAL
    violated_lo: i32,
    violated_hi: i32,
    violated_count: i32,
    passed: bool
}

type constraint_bounds = {
    lo: i32,
    hi: i32
}

// ══════════════════════════════════════════════════════════════════
//  Core Functions
// ══════════════════════════════════════════════════════════════════

let saturate (val: i32) : i32 =
    if val < INT8_MIN then INT8_MIN
    else if val > INT8_MAX then INT8_MAX
    else val

let classify_severity (violated: i32) (total: i32) : i32 =
    if violated == 0 then 0                          // PASS
    else if violated <= total / 4 then 1              // CAUTION
    else if violated <= total / 2 then 2              // WARNING
    else 3                                           // CRITICAL

// ══════════════════════════════════════════════════════════════════
//  Single Value Check — pure function
// ══════════════════════════════════════════════════════════════════

let check_value (bounds: []constraint_bounds) (value: i32) : flux_result =
    let val = saturate value
    let n = length bounds

    -- Check each constraint, accumulating violations
    let (error_mask, violated_lo, violated_hi, violated_count) =
        loop (em, vlo, vhi, vc) = (0i32, 0i32, 0i32, 0i32)
        for i < n do
            let b = bounds[i]
            let lo_fail = val < b.lo
            let hi_fail = val > b.hi
            let any_fail = lo_fail || hi_fail

            let new_em = if any_fail then em | (1 << i) else em
            let new_vlo = if lo_fail then vlo | (1 << i) else vlo
            let new_vhi = if hi_fail then vhi | (1 << i) else vhi
            let new_vc = if any_fail then vc + 1 else vc
            in (new_em, new_vlo, new_vhi, new_vc)

    in {
        error_mask = error_mask,
        severity = classify_severity violated_count n,
        violated_lo = violated_lo,
        violated_hi = violated_hi,
        violated_count = violated_count,
        passed = violated_count == 0
    }

// ══════════════════════════════════════════════════════════════════
//  Batch Check — THIS IS THE GPU PARALLELISM
//  map over all values → each check runs on a different GPU core
//  The compiler turns this into a GPU kernel automatically.
// ══════════════════════════════════════════════════════════════════

let check_batch (bounds: []constraint_bounds) (values: []i32) : []flux_result =
    map (check_value bounds) values

// ══════════════════════════════════════════════════════════════════
//  GPU Accelerated — reduce to get aggregate stats
// ══════════════════════════════════════════════════════════════════

type batch_stats = {
    total: i32,
    passed: i32,
    failed: i32,
    pass_rate: f64
}

let batch_stats (results: []flux_result) : batch_stats =
    let total = length results
    let passed = reduce (+) 0 (map (\r -> if r.passed then 1i32 else 0i32) results)
    let failed = total - passed
    let rate = f64.from_fraction passed total
    in { total = total, passed = passed, failed = failed, pass_rate = rate }

// ══════════════════════════════════════════════════════════════════
//  Error mask extraction — parallel bit reduction
// ══════════════════════════════════════════════════════════════════

let extract_masks (results: []flux_result) : []i32 =
    map (\r -> r.error_mask) results

// Count violations across a batch — reduce on GPU
let total_violations (results: []flux_result) : i32 =
    reduce (+) 0 (map (\r -> r.violated_count) results)

// ══════════════════════════════════════════════════════════════════
//  Industry Presets — as arrays of bounds
// ══════════════════════════════════════════════════════════════════

let aviation_bounds : []constraint_bounds =
    [{lo = -55, hi = 70},    // cabin_temp_C
     {lo = 75, hi = 101},    // cabin_pressure_kPa
     {lo = 0, hi = 100},     // fuel_flow_pct
     {lo = 60, hi = 100}]    // hydraulic_pct

let nuclear_bounds : []constraint_bounds =
    [{lo = 0, hi = 110},     // neutron_flux_pct
     {lo = 0, hi = 65},      // core_temp_C_x10
     {lo = 72, hi = 100},    // pressurizer_pct
     {lo = 0, hi = 100}]     // coolant_flow_pct

let medical_bounds : []constraint_bounds =
    [{lo = 36, hi = 38},     // body_temp_C
     {lo = 60, hi = 100},    // heart_rate_bpm
     {lo = 95, hi = 100},    // spo2_pct
     {lo = 80, hi = 120}]    // bp_systolic_mmHg

let maritime_bounds : []constraint_bounds =
    [{lo = -2, hi = 35},     // sea_temp_C
     {lo = 50, hi = 100},    // hull_integrity_pct
     {lo = 0, hi = 50},      // wave_height_m
     {lo = 0, hi = 80}]      // wind_speed_kn

let energy_bounds : []constraint_bounds =
    [{lo = 49, hi = 51},     // grid_freq_Hz_x10
     {lo = 95, hi = 105},    // voltage_pct
     {lo = 0, hi = 80},      // transformer_temp_C
     {lo = 0, hi = 100}]     // line_load_pct

// ══════════════════════════════════════════════════════════════════
//  Entry Point — what Futhark compiles to a GPU binary
// ══════════════════════════════════════════════════════════════════

let main (values: []i32) : []flux_result =
    check_batch aviation_bounds values

// ══════════════════════════════════════════════════════════════════
//  FUTHARK / GPU INSIGHT
// ══════════════════════════════════════════════════════════════════
//
// CUDA version (what we already have):
//   - Write kernel in CUDA C
//   - Manage memory allocation (cudaMalloc, cudaMemcpy)
//   - Launch kernel with grid/block dimensions
//   - Synchronize, read back results
//   - ~200 lines of boilerplate for a simple check
//
// Futhark version:
//   let check_batch bounds values = map (check_value bounds) values
//   - ONE LINE. The compiler generates the kernel.
//   - Memory management: automatic
//   - Thread synchronization: automatic
//   - Block/grid dimensions: automatic
//   - Even does GPU multi-GPU automatically
//
// Performance: Futhark generates competitive GPU code.
// The constraint check is memory-bound, not compute-bound,
// so pure functional GPU code achieves the same throughput.
//
// The insight: constraint checking is EMBARRASSINGLY PARALLEL.
// Each value is independent. Each constraint is independent.
// This is exactly the pattern functional+GPU languages are built for.
// ══════════════════════════════════════════════════════════════════
