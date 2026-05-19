-- FLUX Constraint Engine — Futhark (2017, GPU-Native Functional)
-- Pure INT8 saturated constraint checking. Zero dependencies.
--
-- The insight: constraint batch checking maps NATURALLY to GPU.
-- Each sensor value is a map operation. Each constraint within is another map.
-- Futhark compiles this to GPU without writing a single CUDA kernel.
-- The programmer thinks in maps. The GPU executes in parallel.
--
-- "Each constraint check is independent. Each batch is a map.
--  Futhark compiles this to GPU without writing a single CUDA kernel."

module flux_constraint

-- ══ Severity ══════════════════════════════════════════════════════

type severity = #pass | #caution | #warning | #critical

-- ══ Data structures ═══════════════════════════════════════════════

type constraint = { lo: i32, hi: i32, name_id: i32 }

type flux_result = { error_mask: u32
                   , sev: severity
                   , violated_lo: u32
                   , violated_hi: u32
                   , violated_count: u32
                   , passed: bool
                   }

-- ══ Constants ════════════════════════════════════════════════════

def INT8_MIN : i32 = -127
def INT8_MAX : i32 = 127
def MAX_CONSTRAINTS : i32 = 8

-- ══ Saturate: clamp to [-127, 127] ═══════════════════════════════

def saturate (v: i32) : i32 =
  if v < INT8_MIN then INT8_MIN
  else if v > INT8_MAX then INT8_MAX
  else v

-- ══ Severity classification ══════════════════════════════════════

def classify_severity (violated: i32) (total: i32) : severity =
  if violated == 0 then #pass
  else if violated <= total / 4 then #caution
  else if violated <= total / 2 then #warning
  else #critical

-- ══ Check all constraints (sequential fold) ═════════════════════

def check (constraints: []constraint) (value: i32) : flux_result =
  let val = saturate value
  let n = length constraints
  let indices = iota n
  -- Map over all constraints in parallel
  let results = map2 (\c i ->
    let lo_fail = val < c.lo
    let hi_fail = val > c.hi
    let failed = lo_fail || hi_fail
    let bit : u32 = u32.i32 (1 << i)
    in ( if failed then bit else 0u32
       , if lo_fail then bit else 0u32
       , if hi_fail then bit else 0u32
       , if failed then 1u32 else 0u32 )
    ) constraints indices
  -- Reduce across all results with commutative reduction
  let (mask, vlo, vhi, vc) =
    reduce_comm (\(m1,lo1,hi1,c1) (m2,lo2,hi2,c2) ->
                   (m1|m2, lo1|lo2, hi1|hi2, c1+c2))
      (0u32, 0u32, 0u32, 0u32)
      results
  in { error_mask = mask
     , sev = classify_severity (i32.u32 vc) n
     , violated_lo = vlo
     , violated_hi = vhi
     , violated_count = vc
     , passed = vc == 0
     }

-- ══ Batch check: GPU-PARALLEL across all values ═════════════════
-- This is the key insight. Each value is independent.
-- Futhark maps this to GPU threads automatically.

entry batch_check (constraints: []constraint) (values: []i32) : []flux_result =
  map (\value -> check constraints value) values

-- ══ Industry presets ═════════════════════════════════════════════

def aviation : []constraint =
  [ {lo = -55, hi = 70,  name_id = 0}   -- cabin_temp_C
  , {lo = 75,  hi = 101, name_id = 1}   -- cabin_pressure_kPa
  , {lo = 0,   hi = 100, name_id = 2}   -- fuel_flow_pct
  , {lo = 60,  hi = 100, name_id = 3}   -- hydraulic_pct
  ]

def nuclear : []constraint =
  [ {lo = 0,  hi = 110, name_id = 0}   -- neutron_flux_pct
  , {lo = 0,  hi = 65,  name_id = 1}   -- core_temp_C_x10
  , {lo = 72, hi = 100, name_id = 2}   -- pressurizer_pct
  , {lo = 0,  hi = 100, name_id = 3}   -- coolant_flow_pct
  ]

def medical : []constraint =
  [ {lo = 36, hi = 38,  name_id = 0}   -- body_temp_C
  , {lo = 60, hi = 100, name_id = 1}   -- heart_rate_bpm
  , {lo = 95, hi = 100, name_id = 2}   -- spo2_pct
  , {lo = 80, hi = 120, name_id = 3}   -- bp_systolic_mmHg
  ]

-- ══ Entry points ════════════════════════════════════════════════

entry check_aviation (value: i32) : flux_result =
  check aviation value

entry batch_aviation (values: []i32) : []flux_result =
  batch_check aviation values

-- ══ Usage ════════════════════════════════════════════════════════
--
-- Compile to GPU:  futhark opencl flux_constraint.fut
-- Compile to CPU:  futhark c flux_constraint.fut
-- Run benchmark:   ./flux_constraint batch_aviation -b < input.dat
--
-- The batch_check entry maps across ALL values on the GPU.
-- Each value triggers a parallel reduction across constraints.
-- No CUDA. No OpenCL kernels. No thread management.
-- Just map and reduce. Futhark does the rest.
--
-- ══ Why Futhark Matters ═════════════════════════════════════════
--
-- Futhark proves that GPU programming doesn't have to be painful.
-- The constraint engine is expressed as pure map/reduce — the most
-- natural parallel pattern. Futhark's compiler generates optimized
-- GPU code that rivals hand-written CUDA.
--
-- For constraint checking specifically:
--   - Each sensor value is independent (embarrassingly parallel)
--   - Each constraint within a value is independent (parallel reduction)
--   - The reduction (OR masks, SUM violations) is associative and commutative
--
-- This means the GPU can schedule checks optimally without ANY hints.
-- The programmer's mental model matches the hardware reality.
