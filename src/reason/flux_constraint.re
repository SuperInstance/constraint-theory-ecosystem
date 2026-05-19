// FLUX Constraint Engine — ReasonML (2016, OCaml's JS-friendly face)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: OCaml's type safety with syntax JavaScript developers can
// read immediately. Variant types for Severity, record types for results,
// pattern matching that the compiler PROVES is exhaustive.
// Compiles to both native AND JavaScript.
//
// "OCaml's type safety, JavaScript's syntax. Engineers read it immediately.
//  Compilers prove it correct."
//
// Usage:
//   bsb -make-world
//   node src/flux_constraint.bs.js
//   OR: dune build && ./flux_constraint.exe

type severity =
  | Pass
  | Caution
  | Warning
  | Critical;

let severityToInt = (s: severity): int =>
  switch (s) {
  | Pass => 0
  | Caution => 1
  | Warning => 2
  | Critical => 3
  };

let severityToString = (s: severity): string =>
  switch (s) {
  | Pass => "PASS"
  | Caution => "CAUTION"
  | Warning => "WARNING"
  | Critical => "CRITICAL"
  };

type constraint = {
  lo: int,
  hi: int,
  name: string,
};

type constraintDetail = {
  name: string,
  lo: int,
  hi: int,
  value: int,
  passed: bool,
  loFailed: bool,
  hiFailed: bool,
};

type fluxResult = {
  errorMask: int,
  severity: severity,
  violatedLo: int,
  violatedHi: int,
  violatedCount: int,
  passed: bool,
  details: list(constraintDetail),
};

// ── Constants ──────────────────────────────────────────────────────

let int8Min = -127;
let int8Max = 127;
let maxConstraints = 8;

// ── Saturate ───────────────────────────────────────────────────────

let saturate = (val: int): int => {
  let v = val;
  if (v < int8Min) { int8Min; } else if (v > int8Max) { int8Max; } else { v; };
};

// ── Severity classification ────────────────────────────────────────

let classifySeverity = (nc: int, vc: int): severity => {
  if (vc == 0) {
    Pass;
  } else if (vc <= nc / 4) {
    Caution;
  } else if (vc <= nc / 2) {
    Warning;
  } else {
    Critical;
  };
};

// ── Check ──────────────────────────────────────────────────────────

let check = (constraints: list(constraint), value: int): option(fluxResult) => {
  let nc = List.length(constraints);
  if (nc == 0 || nc > maxConstraints) {
    None;
  } else {
    let val = saturate(value);

    let rec loop = (cs, i, em, vlo, vhi, vc, acc) => {
      switch (cs) {
      | [] => (em, vlo, vhi, vc, List.rev(acc))
      | [c, ...rest] =>
        let loSat = saturate(c.lo);
        let hiSat = saturate(c.hi);
        let loFail = val < loSat;
        let hiFail = val > hiSat;
        let passed = !loFail && !hiFail;
        let newEm = passed ? em : em lor (1 lsl i);
        let newVlo = loFail ? vlo lor (1 lsl i) : vlo;
        let newVhi = hiFail ? vhi lor (1 lsl i) : vhi;
        let newVc = passed ? vc : vc + 1;
        let detail = {
          name: c.name,
          lo: loSat,
          hi: hiSat,
          value: val,
          passed,
          loFailed: loFail,
          hiFailed: hiFail,
        };
        loop(rest, i + 1, newEm, newVlo, newVhi, newVc, [detail, ...acc]);
      };
    };

    let (errorMask, violatedLo, violatedHi, violatedCount, details) =
      loop(constraints, 0, 0, 0, 0, 0, []);

    let severity = classifySeverity(nc, violatedCount);

    Some({
      errorMask,
      severity,
      violatedLo,
      violatedHi,
      violatedCount,
      passed: violatedCount == 0,
      details,
    });
  };
};

// ── Batch check ────────────────────────────────────────────────────

let checkBatch = (constraints: list(constraint), values: list(int)): list(fluxResult) => {
  switch (check(constraints, 0)) {
  | None => []
  | Some(_) =>
    List.map(v =>
      switch (check(constraints, v)) {
      | Some(r) => r
      | None => assert false
      },
      values
    );
  };
};

// ── Industry Presets ───────────────────────────────────────────────

let aviation: list(constraint) = [
  {lo: -55, hi: 70, name: "cabin_temp_C"},
  {lo: 75, hi: 101, name: "cabin_pressure_kPa"},
  {lo: 0, hi: 100, name: "fuel_flow_pct"},
  {lo: 60, hi: 100, name: "hydraulic_pct"},
];

let medical: list(constraint) = [
  {lo: 36, hi: 38, name: "body_temp_C"},
  {lo: 60, hi: 100, name: "heart_rate_bpm"},
  {lo: 95, hi: 100, name: "spo2_pct"},
  {lo: 80, hi: 120, name: "bp_systolic_mmHg"},
];

let nuclear: list(constraint) = [
  {lo: 0, hi: 110, name: "neutron_flux_pct"},
  {lo: 0, hi: 65, name: "core_temp_C_x10"},
  {lo: 72, hi: 100, name: "pressurizer_pct"},
  {lo: 0, hi: 100, name: "coolant_flow_pct"},
];

let automotive: list(constraint) = [
  {lo: -40, hi: 60, name: "battery_temp_C"},
  {lo: 0, hi: 100, name: "soc_pct"},
  {lo: 0, hi: 100, name: "charge_rate_pct"},
  {lo: 20, hi: 80, name: "cabin_temp_C"},
];

// ── Demo ───────────────────────────────────────────────────────────

let () = {
  Js.log("═══ FLUX Constraint Engine — ReasonML ═══");
  Js.log("");

  switch (check(aviation, 60)) {
  | Some(r) =>
    Js.log("  Aviation val=60: " ++ severityToString(r.severity)
           ++ " mask=0x" ++ string_of_int(r.errorMask)
           ++ " passed=" ++ string_of_bool(r.passed));
  | None => Js.log("  Invalid constraints");
  };

  switch (check(aviation, 25)) {
  | Some(r) =>
    Js.log("  Aviation val=25: " ++ severityToString(r.severity)
           ++ " passed=" ++ string_of_bool(r.passed));
  | None => ();
  };

  switch (check(nuclear, -10)) {
  | Some(r) =>
    Js.log("  Nuclear val=-10: " ++ severityToString(r.severity)
           ++ " mask=0x" ++ string_of_int(r.errorMask)
           ++ " passed=" ++ string_of_bool(r.passed));
  | None => ();
  };

  /* Batch test */
  let batchResults = checkBatch(aviation, [-60, 0, 25, 70, 90, 127]);
  Js.log("\n  Batch: " ++ string_of_int(List.length(batchResults)) ++ " results");
  List.iter(r => {
    Js.log("    sev=" ++ severityToString(r.severity) ++ " passed=" ++ string_of_bool(r.passed));
  }, batchResults);
};
