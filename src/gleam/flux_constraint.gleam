// FLUX Constraint Engine — Gleam
// Pure INT8 saturated constraint checking. Type-safe, zero dependencies.

import gleam/int
import gleam/io
import gleam/list

const int8_min = -127
const int8_max = 127

pub fn saturate(val: Int) -> Int {
  case val <. int8_min, val >. int8_max {
    True, _ -> int8_min
    _, True -> int8_max
    _, _ -> val
  }
}

pub type Severity {
  Pass
  Caution
  Warning
  Critical
}

pub type Constraint {
  Constraint(lo: Int, hi: Int, name: String)
}

pub type FluxResult {
  FluxResult(
    error_mask: Int,
    severity: Severity,
    violated_lo: Int,
    violated_hi: Int,
    violated_count: Int,
    passed: Bool,
  )
}

pub fn check(constraints: List(Constraint), value: Int) -> FluxResult {
  let val = saturate(value)
  let #(em, vlo, vhi, vc) = list.index_fold(
    constraints,
    #(0, 0, 0, 0),
    fn(acc, c, i) {
      let #(em, vlo, vhi, vc) = acc
      let lo = saturate(c.lo)
      let hi = saturate(c.hi)
      let lo_fail = val < lo
      let hi_fail = val > hi
      let bit = int.bitwise_shift_left(1, i)
      #(
        case lo_fail || hi_fail {
          True -> int.bitwise_or(em, bit)
          False -> em
        },
        case lo_fail {
          True -> int.bitwise_or(vlo, bit)
          False -> vlo
        },
        case hi_fail {
          True -> int.bitwise_or(vhi, bit)
          False -> vhi
        },
        case lo_fail || hi_fail {
          True -> vc + 1
          False -> vc
        },
      )
    },
  )

  let nc = list.length(constraints)
  let sev = case vc {
    0 -> Pass
    v if v <= nc / 4 -> Caution
    v if v <= nc / 2 -> Warning
    _ -> Critical
  }

  FluxResult(
    error_mask: em,
    severity: sev,
    violated_lo: vlo,
    violated_hi: vhi,
    violated_count: vc,
    passed: sev == Pass,
  )
}

pub fn main() {
  io.println("FLUX Constraint Engine — Gleam")
  io.println("==============================")

  let assert -127 = saturate(-128)
  let assert 127 = saturate(128)
  io.println("  saturate: OK")

  let r1 = check([Constraint(0, 100, "test")], 50)
  let assert True = r1.passed
  let r2 = check([Constraint(0, 100, "test")], 150)
  let assert False = r2.passed
  io.println("  check: OK")

  let fc4 = [
    Constraint(0, 10, "a"), Constraint(0, 10, "b"),
    Constraint(0, 10, "c"), Constraint(0, 10, "d"),
  ]
  let r3 = check(fc4, 50)
  let assert Critical = r3.severity
  let assert 4 = r3.violated_count
  io.println("  severity: OK")

  io.println("  All tests pass")
}
