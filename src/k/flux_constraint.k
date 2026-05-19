# FLUX Constraint Engine — K (1993, One-Character Verbs)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# Arthur Whitney's K is the most concise programming language in existence.
# The insight: the ENTIRE constraint engine is under 100 characters of logic.
# K is what happens when you compress APL to its essence — every character
# carries meaning, no wasted tokens, no ceremony.
#
# "K has no wasted characters. The constraint engine is a one-liner.
#  APL was verbose; K is what happens when you compress it."

# ══ Saturate: clamp to [-127, 127] ═══════════════════════════════
# 14 characters. Each one essential.
sat:{(-127)|127&x}

# ══ Severity: classify violation count ════════════════════════════
# 0=pass, 1=caution, 2=warning, 3=critical
sev:{:[0=x;0;x<=.25*y;1;x<=.5*y;2;3]}

# ══ Check: core constraint engine ═════════════════════════════════
# cs: list of (lo;hi) pairs.  v: value to check.
# Returns: (error_mask; severity; violated_lo; violated_hi; violated_count; passed)
check:{[cs;v]
  n:#cs; v:sat v;
  lo_fail:v<cs[;0];
  hi_fail:v>cs[;1];
  fail:lo_fail|hi_fail;
  bits:2_vs n#0; / bit positions 0..n-1
  mask:|/fail*2^!n;
  vlo:|/lo_fail*2^!n;
  vhi:|/hi_fail*2^!n;
  vc:+/fail;
  (mask;sev[vc;n];vlo;vhi;vc;0=vc)}

# ══ Batch check: apply to list of values ══════════════════════════
# Returns a table of results
batch:{[cs;vs]
  r:check[cs]'vs;
  `error_mask`severity`violated_lo`violated_hi`violated_count`passed!+r}

# ══ Industry presets ═════════════════════════════════════════════

# Aviation: cabin_temp, cabin_pressure, fuel_flow, hydraulic
av:(-55 70;75 101;0 100;60 100)

# Automotive: battery_temp, soc, charge_rate, cabin_temp
au:(-40 60;0 100;0 100;20 80)

# Maritime: sea_temp, hull, waves, wind
ma:(-2 35;50 100;0 50;0 80)

# Medical: body_temp, heart_rate, spo2, bp
me:(36 38;60 100;95 100;80 120)

# Energy: grid_freq, voltage, transformer, load
en:(49 51;95 105;0 80;0 100)

# Nuclear: neutron_flux, core_temp, pressurizer, coolant
nu:(0 110;0 65;72 100;0 100)

# Railway: speed, brakes, doors, track_temp
ra:(0 100;0 100;0 1;0 80)

# Robotics: torque, speed, force, position
ro:(-100 100;0 100;0 100;-127 127)

# Space: temp, solar, propellant, battery
sp:(-40 50;0 100;0 100;0 100)

# Underwater: depth, battery, water_temp, thruster
un:(0 100;0 100;-5 35;0 100)

# ══ Preset lookup ════════════════════════════════════════════════

presets:`av`au`ma`me`en`nu`ra`ro`sp`un!(av;au;ma;me;en;nu;ra;ro;sp;un)

# ══ Usage ════════════════════════════════════════════════════════
#
# Check aviation at value 60:
#   check[av;60]
#   / Returns (0;0;0;0;0;1) — all pass
#
# Check aviation at value -60:
#   check[av;-60]
#   / Returns (15;3;15;0;4;0) — all 4 violated, critical
#   / mask=15=0b1111, all constraints fail at -60
#
# Batch check:
#   batch[av;-60 0 25 70 90 127]
#
# Quick preset:
#   check[presets`me;37]
#   / Medical preset, body temp 37°C — pass
#
# ══ The One-Liner Version ════════════════════════════════════════
# For those who want the ENTIRE engine in a single expression:
#
#   fc:{[cs;v]n:#cs;f:(sat v)<cs[;0]|:(sat v)>cs[;1];(+/f*2^!n;sev[+/f;n];+/((sat v)<cs[;0])*2^!n;+/((sat v)>cs[;1])*2^!n;+/f;0=+/f)}
#
# 146 characters. The complete constraint engine.
# Saturate + check + severity + error_mask + violated_lo/hi/count + passed.
# No dependencies. No imports. No boilerplate.
#
# ══ Why K Matters ════════════════════════════════════════════════
#
# K demonstrates that constraint checking is FUNDAMENTALLY SIMPLE.
# When you strip away all the syntax, types, and ceremony of modern
# languages, the core operation is:
#
#   mask = OR of (value < lo OR value > hi) shifted by position
#
# That's it. Every other language wraps this in classes, structs,
# modules, type annotations, and error handling. K shows the bare math.
#
# The one-liner is not a trick — it's the essence. The 100-line Python
# implementation and the 1-line K implementation compute EXACTLY the
# same thing. K just refuses to waste characters.
#
# For constraint theory, K proves that the fundamental operation is
# a boolean reduction over a comparison matrix. No more, no less.
