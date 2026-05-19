// FLUX Constraint Engine — Io (2002, Prototype-based OOP)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: no classes, only prototypes. Constraint checkers are cloned
// and customized. Delegation chain IS the constraint hierarchy.
// A nuclear checker can clone an aviation checker and ADD more constraints.
// Introspection is free — every slot is queryable at runtime.
//
// "No classes. Only prototypes and delegation. Clone a checker, customize it.
//  The prototype chain IS the constraint hierarchy."
//
// Usage:
//   io flux_constraint.io

// ══ Constants ════════════════════════════════════════════════════════

INT8_MIN := -127
INT8_MAX := 127
MAX_CONSTRAINTS := 8

// ══ Severity ════════════════════════════════════════════════════════

Severity := Object clone
Severity levels := list("PASS", "CAUTION", "WARNING", "CRITICAL")

// ══ ConstraintDetail ════════════════════════════════════════════════

ConstraintDetail := Object clone
ConstraintDetail name := ""
ConstraintDetail lo := 0
ConstraintDetail hi := 0
ConstraintDetail value := 0
ConstraintDetail passed := true
ConstraintDetail loFailed := false
ConstraintDetail hiFailed := false

// ══ FluxResult ══════════════════════════════════════════════════════

FluxResult := Object clone
FluxResult errorMask := 0
FluxResult severity := 0
FluxResult severityName := "PASS"
FluxResult violatedLo := 0
FluxResult violatedHi := 0
FluxResult violatedCount := 0
FluxResult passed := true
FluxResult details := list()

FluxResult println := method(
  "  severity=" .. severityName .. " mask=0x" .. errorMask asHex .. 
  " violated=" .. violatedCount asString .. " passed=" .. passed asString
  println
)

// ══ Constraint ══════════════════════════════════════════════════════

Constraint := Object clone
Constraint lo := 0
Constraint hi := 0
Constraint name := ""

Constraint saturate := method(val,
  if(val < INT8_MIN, INT8_MIN,
    if(val > INT8_MAX, INT8_MAX, val)
  )
)

Constraint init := method(
  lo = 0
  hi = 0
  name = ""
  self
)

Constraint with := method(loVal, hiVal, nameStr,
  c := self clone
  c lo = self saturate(loVal)
  c hi = self saturate(hiVal)
  c name = nameStr
  c
)

// ══ FluxChecker ═════════════════════════════════════════════════════

FluxChecker := Object clone
FluxChecker constraints := list()

FluxChecker saturate := method(val,
  if(val < INT8_MIN, INT8_MIN,
    if(val > INT8_MAX, INT8_MAX, val)
  )
)

FluxChecker addConstraint := method(loVal, hiVal, nameStr,
  c := Constraint with(loVal, hiVal, nameStr)
  constraints append(c)
  self
)

FluxChecker check := method(value,
  val := self saturate(value)
  nc := constraints size
  
  if(nc == 0,
    Exception raise("No constraints defined")
  )
  if(nc > MAX_CONSTRAINTS,
    Exception raise("Max 8 constraints")
  )
  
  result := FluxResult clone
  em := 0
  vlo := 0
  vhi := 0
  vc := 0
  detailList := list()
  
  constraints foreach(i, c,
    loFail := val < c lo
    hiFail := val > c hi
    passed := (not loFail) and (not hiFail)
    
    if(not passed,
      em = em + (2 ** i)
      vc = vc + 1
    )
    if(loFail,
      vlo = vlo + (2 ** i)
    )
    if(hiFail,
      vhi = vhi + (2 ** i)
    )
    
    d := ConstraintDetail clone
    d name = c name
    d lo = c lo
    d hi = c hi
    d value = val
    d passed = passed
    d loFailed = loFail
    d hiFailed = hiFail
    detailList append(d)
  )
  
  // Classify severity
  sevName := if(vc == 0, "PASS",
    if(vc <= (nc / 4), "CAUTION",
      if(vc <= (nc / 2), "WARNING", "CRITICAL"
      )
    )
  )
  sevLevel := if(vc == 0, 0,
    if(vc <= (nc / 4), 1,
      if(vc <= (nc / 2), 2, 3)
    )
  )
  
  result errorMask = em
  result severity = sevLevel
  result severityName = sevName
  result violatedLo = vlo
  result violatedHi = vhi
  result violatedCount = vc
  result passed = (vc == 0)
  result details = detailList
  result
)

FluxChecker checkBatch := method(values,
  results := list()
  values foreach(v,
    results append(self check(v))
  )
  results
)

// ══ Industry Presets ════════════════════════════════════════════════

FluxChecker aviation := method(
  fc := FluxChecker clone
  fc addConstraint(-55, 70, "cabin_temp_C")
  fc addConstraint(75, 101, "cabin_pressure_kPa")
  fc addConstraint(0, 100, "fuel_flow_pct")
  fc addConstraint(60, 100, "hydraulic_pct")
  fc
)

FluxChecker medical := method(
  fc := FluxChecker clone
  fc addConstraint(36, 38, "body_temp_C")
  fc addConstraint(60, 100, "heart_rate_bpm")
  fc addConstraint(95, 100, "spo2_pct")
  fc addConstraint(80, 120, "bp_systolic_mmHg")
  fc
)

FluxChecker nuclear := method(
  fc := FluxChecker clone
  fc addConstraint(0, 110, "neutron_flux_pct")
  fc addConstraint(0, 65, "core_temp_C_x10")
  fc addConstraint(72, 100, "pressurizer_pct")
  fc addConstraint(0, 100, "coolant_flow_pct")
  fc
)

FluxChecker automotive := method(
  fc := FluxChecker clone
  fc addConstraint(-40, 60, "battery_temp_C")
  fc addConstraint(0, 100, "soc_pct")
  fc addConstraint(0, 100, "charge_rate_pct")
  fc addConstraint(20, 80, "cabin_temp_C")
  fc
)

FluxChecker maritime := method(
  fc := FluxChecker clone
  fc addConstraint(-2, 35, "sea_temp_C")
  fc addConstraint(50, 100, "hull_integrity_pct")
  fc addConstraint(0, 50, "wave_height_m")
  fc addConstraint(0, 80, "wind_speed_kn")
  fc
)

// ══ Delegation example ═════════════════════════════════════════════
// Clone aviation and ADD radiation monitoring for high-altitude flights

HighAltChecker := FluxChecker aviation
HighAltChecker addConstraint(0, 50, "radiation_mSv_h")
// Now has 5 constraints: aviation 4 + radiation 1

// ══ Main ════════════════════════════════════════════════════════════

"═══ FLUX Constraint Engine — Io (Prototype-based) ═══" println
"" println

// Aviation tests
fc := FluxChecker aviation
"Aviation preset: 4 constraints" println

r := fc check(60)
"  val=60: " print .. r println

r := fc check(25)
"  val=25: " print .. r println

r := fc check(-60)
"  val=-60: " print .. r println

"" println

// Medical tests
med := FluxChecker medical
"Medical preset: 4 constraints" println

r := med check(37)
"  val=37: " print .. r println

r := med check(42)
"  val=42: " print .. r println

"" println

// Nuclear tests
nuc := FluxChecker nuclear
"Nuclear preset: 4 constraints" println

r := nuc check(80)
"  val=80: " print .. r println

"" println

// Delegation: high-altitude checker
"High-altitude checker (aviation + radiation):" println
r := HighAltChecker check(60)
"  val=60: " print .. r println

"" println

// Batch test
"Batch test (aviation, 6 values):" println
results := fc checkBatch(list(-60, 0, 25, 70, 90, 127))
results foreach(i, r,
  "  [" .. i asString .. "] " .. r severityName .. " passed=" .. r passed asString println
)

"" println

// Introspection: show all slots on a checker
"FluxChecker slots:" println
fc slotSummary println
