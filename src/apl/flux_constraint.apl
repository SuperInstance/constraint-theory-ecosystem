⍝ FLUX Constraint Engine — APL (1966, Array Language)
⍝ Pure INT8 saturated constraint checking. Zero dependencies.
⍝
⍝ The insight: constraint checking IS a rank-1 array operation.
⍝ No loops. No iteration. The entire batch is one expression.
⍝ APL saw this in 1966 — 60 years before "vectorized ML pipelines."
⍝
⍝ Usage:
⍝   cons ← 4 2⍴¯55 70 75 101 0 100 60 100
⍝   names ← 'cabin_temp' 'cabin_press' 'fuel_flow' 'hydraulic'
⍝   r ← cons flux_check 60
⍝   r.error_mask    ⍝ → 1
⍝   r.severity      ⍝ → 1 (CAUTION)
⍝
⍝ Batch: r ← cons flux_check ¯60 0 25 70 127

⍝ ── Saturate: clamp to [-127, 127] ──────────────────────────────────
⍝ APL idiom: 127⌊¯127⌈x  (max(-127, min(127, x)))

sat ← {127 ⌊ ¯127 ⌈ ⍵}

⍝ ── Core: check value(s) against constraint matrix ──────────────────
⍝ cons = N×2 matrix [lo, hi]  — up to 8 rows
⍝ val  = scalar or vector of saturated INT8 values
⍝ Returns: namespace with all FLUX result fields

flux_check ← {
    n ← 1⌈⍴⍺                           ⍝ number of constraints
    v ← sat ⍵                            ⍝ saturate input(s)
    lo ← ⍺[;1]                           ⍝ lower bounds
    hi ← ⍺[;2]                           ⍝ upper bounds

    ⍝ Rank magic: (⍴v) × (⍴lo) — outer comparison
    ⍝ Each row = one constraint, each col = one input value
    lo_fail ← v ∘.< lo                   ⍝ value below lower bound
    hi_fail ← v ∘.> hi                   ⍝ value above upper bound
    any_fail ← lo_fail ∨ hi_fail         ⍝ either violation

    ⍝ Bit vectors → packed error masks (power-of-2 weighted sum)
    bits ← ⍳n
    emask ← any_fail +.× (2*bits)        ⍝ dot product with powers of 2

    ⍝ Severity: ratio of violated constraints
    vc ← +/any_fail                      ⍝ violation count per value
    sev ← (vc=0) + 1×(0<vc)∧(vc≤⌊n÷4) + 2×(vc>⌊n÷4)∧(vc≤⌊n÷2) + 3×(vc>⌊n÷2)
    ⍝ Simplified: 0=PASS 1=CAUTION 2=WARNING 3=CRITICAL

    lo_mask ← lo_fail +.× (2*bits)
    hi_mask ← hi_fail +.× (2*bits)

    ⍝ Return namespace with all FLUX fields
    r ← ⎕NS ''
    r.error_mask ← emask
    r.severity ← sev
    r.violated_lo ← lo_mask
    r.violated_hi ← hi_mask
    r.violated_count ← vc
    r.passed ← vc = 0
    r
}

⍝ ── Industry presets (constraint matrices) ─────────────────────────

aviation ← 4 2⍴ ¯55 70 75 101 0 100 60 100
⍝ cabin_temp_C[-55,70] cabin_pressure_kPa[75,101] fuel_flow_pct[0,100] hydraulic_pct[60,100]

automotive ← 4 2⍴ ¯40 60 0 100 0 100 20 80
⍝ battery_temp_C[-40,60] soc_pct[0,100] charge_rate_pct[0,100] cabin_temp_C[20,80]

maritime ← 4 2⍴ ¯2 35 50 100 0 50 0 80
⍝ sea_temp_C[-2,35] hull_integrity_pct[50,100] wave_height_m[0,50] wind_speed_kn[0,80]

medical ← 4 2⍴ 36 38 60 100 95 100 80 120
⍝ body_temp_C[36,38] heart_rate_bpm[60,100] spo2_pct[95,100] bp_systolic_mmHg[80,120]

energy ← 4 2⍴ 49 51 95 105 0 80 0 100
⍝ grid_freq_Hz_x10[49,51] voltage_pct[95,105] transformer_temp_C[0,80] line_load_pct[0,100]

nuclear ← 4 2⍴ 0 110 0 65 72 100 0 100
⍝ neutron_flux_pct[0,110] core_temp_C_x10[0,65] pressurizer_pct[72,100] coolant_flow_pct[0,100]

railway ← 4 2⍴ 0 100 0 100 0 1 0 80
⍝ speed_pct[0,100] brake_pressure_pct[0,100] door_interlock[0,1] track_temp_C[0,80]

robotics ← 4 2⍴ ¯100 100 0 100 0 100 ¯127 127
⍝ joint_torque_pct[-100,100] speed_pct[0,100] force_pct[0,100] position_mm[-127,127]

space ← 4 2⍴ ¯40 50 0 100 0 100 0 100
⍝ temp_C[-40,50] solar_panel_pct[0,100] propellant_pct[0,100] battery_pct[0,100]

underwater ← 4 2⍴ 0 100 0 100 ¯5 35 0 100
⍝ depth_pct[0,100] battery_pct[0,100] water_temp_C[-5,35] thruster_pct[0,100]

⍝ ── Example usage ──────────────────────────────────────────────────

⍝ Single value check against aviation preset:
⍝   r ← aviation flux_check 60
⍝   r.error_mask     ⍝ bit vector of violations
⍝   r.passed         ⍝ 1 if all pass, 0 otherwise
⍝   r.severity       ⍝ 0=PASS 1=CAUTION 2=WARNING 3=CRITICAL

⍝ Batch check — the array way:
⍝   vals ← ¯60 0 25 70 127
⍝   results ← aviation flux_check vals
⍝   results.error_mask    ⍝ one mask per value
⍝   results.violated_count ⍝ violations per value

⍝ "The whole check is one expression. Loops are a code smell in array languages."
⍝ — APL, 1966: the original insight that computation IS structure.
