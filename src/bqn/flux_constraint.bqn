# FLUX Constraint Engine — BQN (2022, Modern Array Language)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# The insight: the entire constraint check is ONE glyph expression.
# BQN is the successor to APL/J/K — array-first, glyph-rich, mathematically
# precise. Where other languages loop, BQN ranks. Where they branch,
# BQN selects. The whole check: (v ∘.< lo) ∨ (v ∘.> hi) → mask.
# That's it. One expression. Batch by default.
#
# "The whole check is one expression. Loops are a code smell in array languages."

# ══ Constants ═══════════════════════════════════════════════════════

INT8_MIN ← ¯127
INT8_MAX ← 127

# ══ Saturate: one glyph expression ═══════════════════════════════
# BQN idiom: INT8_MAX ⌊ INT8_MIN ⌈ x
# Read right-to-left: max(-127, min(127, x))

Sat ← INT8_MAX ⌊ INT8_MIN ⌈⊢

# ══ Core: constraint check — TACIT STYLE ═════════════════════════
# Input: cons = N×2 array [lo, hi], val = scalar or vector
# Output: namespace with all FLUX result fields

FluxCheck ← {
  # Saturate input
  v ← Sat 𝕨
  # cons: each row = [lo, hi]
  lo ← ⊏⟜(0⊸⊑) 𝕩    # first column = lower bounds
  hi ← ⊏⟜(1⊸⊑) 𝕩    # second column = upper bounds
  n ← ≠lo            # number of constraints

  # THE expression: outer comparison (Rank magic)
  # (⍴v) × (⍴lo) result — each row = constraint, each col = input value
  lo_fail ← v ∘.< lo
  hi_fail ← v ∘.> hi
  any_fail ← lo_fail ∨ hi_fail

  # Bit masks: weighted sum with powers of 2
  bits ← 2⋆↕n
  emask ← any_fail +˝∘×⌜⟜bits    # dot: weighted sum across constraints
  lo_mask ← lo_fail +˝∘×⌜⟜bits
  hi_mask ← hi_fail +˝∘×⌜⟜bits

  # Violation counts per value (sum across constraints)
  vc ← +˝any_fail

  # Severity: 0=PASS 1=CAUTION 2=WARNING 3=CRITICAL
  # Tacit severity classification using binning
  sev ← {𝕊 vc n:
    0⊸=◶(0⊸⊑)‿(vc≤⌊n÷4)◶(1⊸⊑)‿(vc≤⌊n÷2)◶(2⊸⊑)‿3⊸⊑ vc
  }⟜n

  # Actually simpler:
  sev ← (vc=0)×0 + (0<vc)×(1+vc>⌊n÷4)+(vc>⌊n÷2)

  # Return as a namespace (BQN namespace = block returning a list)
  ⟨emask, sev, lo_mask, hi_mask, vc, vc=0⟩
}

# ══ Explicit style version (more readable) ════════════════════════

FluxCheckExplicit ← {
  v ← Sat 𝕨
  lo ← (<˘2⊸↕) 𝕩     # column 0
  hi ← (>˘2⊸↕) 𝕩     # column 1

  lo_fail ← v ∘.< lo
  hi_fail ← v ∘.> hi
  any_fail ← lo_fail ∨ hi_fail

  n ← ≠lo
  bits ← 2⋆↕n

  emask ← {𝕩 +´∘× bits}¨ ∘.≍⟜↕∘≠ any_fail
  # Simpler: just use matrix multiply
  emask ← any_fail (+˝×⌜) bits
  lo_mask ← lo_fail (+˝×⌜) bits
  hi_mask ← hi_fail (+˝×⌜) bits

  vc ← +˝any_fail

  ⟨emask, vc⟩
}

# ══ Industry presets ═══════════════════════════════════════════════

aviation ← 4‿2⥊¯55‿70‿75‿101‿0  100‿60‿100
# cabin_temp_C[-55,70] cabin_pressure_kPa[75,101] fuel_flow[0,100] hydraulic[60,100]

automotive ← 4‿2⥊¯40‿60‿0‿100‿0  100‿20‿80
# battery_temp[-40,60] soc[0,100] charge_rate[0,100] cabin[20,80]

maritime ← 4‿2⥊¯2‿35‿50  100‿0  50‿0  80
# sea_temp[-2,35] hull[50,100] waves[0,50] wind[0,80]

medical ← 4‿2⥊36‿38‿60  100‿95  100‿80  120
# body_temp[36,38] heart_rate[60,100] spo2[95,100] bp[80,120]

energy ← 4‿2⥊49‿51‿95  105‿0  80‿0  100
# grid_freq[49,51] voltage[95,105] transformer[0,80] load[0,100]

nuclear ← 4‿2⥊0  110‿0  65‿72  100 0  100
# neutron_flux[0,110] core_temp[0,65] pressurizer[72,100] coolant[0,100]

railway ← 4‿2⥊0  100‿0  100‿0  1  0  80
# speed[0,100] brakes[0,100] door[0,1] track[0,80]

robotics ← 4‿2⥊¯100‿100 0  100‿0  100‿¯127 127
# torque[-100,100] speed[0,100] force[0,100] position[-127,127]

space ← 4‿2⥊¯40 50‿0  100‿0  100 0  100
# temp[-40,50] solar[0,100] propellant[0,100] battery[0,100]

underwater ← 4‿2⥊0  100 0  100‿¯5 35‿0  100
# depth[0,100] battery[0,100] water_temp[-5,35] thruster[0,100]

# ══ Usage examples ═════════════════════════════════════════════════

# Single value:
#   60 FluxCheck aviation
#   → ⟨1, 1, 0, 1, 1, 0⟩  (CAUTION, 1 violation, mask=0x01)

# Batch — arrays are first-class, batch is DEFAULT:
#   ¯60‿0‿25‿70‿127 FluxCheck aviation
#   → arrays of masks, counts, severities

# "The whole check is one expression.
#  Sat ← 127⌊¯127⌈⊢         — saturate in 5 glyphs
#  v∘.<lo ∨ v∘.>hi          — all violations, all values, one expression
#  Batch checking is the DEFAULT — BQN doesn't know what 'scalar only' means.
#  APL had this insight in 1966. BQN perfected it in 2022."
