# FLUX Constraint Engine — Nim
# Pure INT8 saturated constraint checking. Zero dependencies.

const
  Int8Min* = -127
  Int8Max* = 127

type
  Severity* = enum
    Pass = 0, Caution = 1, Warning = 2, Critical = 3

  Constraint* = object
    lo*, hi*: int
    name*: string

  FluxResult* = object
    errorMask*: int
    severity*: Severity
    violatedLo*: int
    violatedHi*: int
    violatedCount*: int
    passed*: bool

  FluxChecker* = object
    constraints*: seq[Constraint]

proc saturate*(val: int): int =
  result = val
  if result < Int8Min: result = Int8Min
  elif result > Int8Max: result = Int8Max

proc newFluxChecker*(constraints: seq[Constraint]): FluxChecker =
  doAssert constraints.len > 0, "Non-empty constraints required"
  doAssert constraints.len <= 8, "Max 8 constraints"
  result = FluxChecker(constraints: constraints)

proc check*(fc: FluxChecker, value: int): FluxResult =
  let val = saturate(value)
  var emask, vlo, vhi, vcount = 0

  for i, c in fc.constraints:
    let lo = saturate(c.lo)
    let hi = saturate(c.hi)
    let loFail = val < lo
    let hiFail = val > hi
    if loFail or hiFail:
      emask = emask or (1 shl i)
      vcount.inc
    if loFail: vlo = vlo or (1 shl i)
    if hiFail: vhi = vhi or (1 shl i)

  let nc = fc.constraints.len
  let sev = if vcount == 0: Pass
            elif vcount <= nc div 4: Caution
            elif vcount <= nc div 2: Warning
            else: Critical

  FluxResult(
    errorMask: emask, severity: sev,
    violatedLo: vlo, violatedHi: vhi,
    violatedCount: vcount, passed: sev == Pass
  )

proc checkBatch*(fc: FluxChecker, values: seq[int]): (seq[FluxResult], array[4, int]) =
  var results = newSeq[FluxResult](values.len)
  var stats: array[4, int]
  for i, v in values:
    results[i] = fc.check(v)
    stats[ord(results[i].severity)].inc
  (results, stats)

proc benchmark*(fc: FluxChecker, iterations = 1_000_000): (float, float) =
  let t0 = cpuTime()
  for i in 0..<iterations:
    discard fc.check((i mod 254) - 127)
  let elapsed = cpuTime() - t0
  let rate = float(iterations * fc.constraints.len) / elapsed
  (rate, elapsed * 1000.0)

# Presets
const Presets* = {
  "aviation": @[
    Constraint(lo: -55, hi: 70, name: "cabin_temp_C"),
    Constraint(lo: 75, hi: 101, name: "cabin_pressure_kPa"),
    Constraint(lo: 0, hi: 100, name: "fuel_flow_pct"),
    Constraint(lo: 60, hi: 100, name: "hydraulic_pct"),
  ],
  "medical": @[
    Constraint(lo: 36, hi: 38, name: "body_temp_C"),
    Constraint(lo: 60, hi: 100, name: "heart_rate_bpm"),
    Constraint(lo: 95, hi: 100, name: "spo2_pct"),
    Constraint(lo: 80, hi: 120, name: "bp_systolic_mmHg"),
  ],
  "automotive": @[
    Constraint(lo: -40, hi: 60, name: "battery_temp_C"),
    Constraint(lo: 0, hi: 100, name: "soc_pct"),
    Constraint(lo: 0, hi: 100, name: "charge_rate_pct"),
    Constraint(lo: 20, hi: 80, name: "cabin_temp_C"),
  ],
}.toTable

proc fromPreset*(name: string): FluxChecker =
  newFluxChecker(Presets[name])

when isMainModule:
  import std/tables
  echo "FLUX Constraint Engine — Nim"
  echo "============================"

  assert saturate(-128) == -127
  assert saturate(128) == 127
  echo "  saturate: OK"

  let fc = newFluxChecker(@[Constraint(lo: 0, hi: 100, name: "test")])
  assert fc.check(50).passed
  assert not fc.check(150).passed
  echo "  check: OK"

  let fc2 = newFluxChecker(@[
    Constraint(lo: 0, hi: 10), Constraint(lo: 0, hi: 10),
    Constraint(lo: 0, hi: 10), Constraint(lo: 0, hi: 10)])
  let r = fc2.check(50)
  assert r.severity == Critical and r.violatedCount == 4
  echo "  severity: OK"

  echo "  All tests pass"
