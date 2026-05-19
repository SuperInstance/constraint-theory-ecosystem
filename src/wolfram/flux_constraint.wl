(* FLUX Constraint Engine — Wolfram (1988, Symbolic Computation) *)
(* Pure INT8 saturated constraint checking. Zero dependencies. *)
(* *)
(* The insight: Wolfram is SYMBOLIC. Constraints aren't just checked — *)
(* they're SIMPLIFIED. Simplify[constraint] gives you the minimal form. *)
(* Symbolic reduction finds contradictions automatically. *)
(* "If Simplify returns False, the constraint is impossible. *)
(*  If it returns True, it's trivially satisfied. *)
(*  Everything in between is the interesting part." *)

(* ══ Constants ══════════════════════════════════════════════════════ *)

int8Min = -127;
int8Max = 127;
maxConstraints = 8;

(* ══ Saturate ══════════════════════════════════════════════════════ *)

saturate[val_Integer] := Clip[val, {int8Min, int8Max}]

(* ══ Severity ══════════════════════════════════════════════════════ *)

severityNames = {0 -> "PASS", 1 -> "CAUTION", 2 -> "WARNING", 3 -> "CRITICAL"};

classifySeverity[vc_Integer, n_Integer] :=
  Which[
    vc == 0,          0,  (* PASS *)
    vc <= Quotient[n, 4], 1,  (* CAUTION *)
    vc <= Quotient[n, 2], 2,  (* WARNING *)
    True,             3   (* CRITICAL *)
  ]

(* ══ Constraint structures ══════════════════════════════════════════ *)
(* In Wolfram, constraints are SYMBOLIC EXPRESSIONS. *)
(* A constraint like "battery_temp in [15, 55]" becomes: *)
(*   15 <= battery_temp <= 55 *)
(* And you can Simplify, Reduce, and Solve with it. *)

(* ══ Core check ═══════════════════════════════════════════════════ *)

fluxCheck[constraints_List, rawVal_Integer] := Module[
  {val, n, results, loFails, hiFails, anyFails, em, vlo, vhi, vc, sev},
  val = saturate[rawVal];
  n = Length[constraints];
  
  (* Each constraint is {lo, hi, name} *)
  loFails = Map[(val < #[[1]]) &, constraints];
  hiFails = Map[(val > #[[2]]) &, constraints];
  anyFails = MapThread[Or, {loFails, hiFails}];
  
  (* Error mask as bit vector *)
  em = Sum[If[anyFails[[i]], 2^(i-1), 0], {i, 1, n}];
  vlo = Sum[If[loFails[[i]], 2^(i-1), 0], {i, 1, n}];
  vhi = Sum[If[hiFails[[i]], 2^(i-1), 0], {i, 1, n}];
  vc = Count[anyFails, True];
  sev = classifySeverity[vc, n];
  
  <|
    "errorMask" -> em,
    "severity" -> sev,
    "severityName" -> (sev /. severityNames),
    "violatedLo" -> vlo,
    "violatedHi" -> vhi,
    "violatedCount" -> vc,
    "passed" -> (vc == 0)
  |>
]

(* ══ Batch check ══════════════════════════════════════════════════ *)

fluxBatchCheck[constraints_List, values_List] :=
  Map[(fluxCheck[constraints, #]) &, values]

(* ══ SYMBOLIC constraint analysis ═════════════════════════════════ *)
(* This is Wolfram's UNIQUE contribution. We can analyze constraints *)
(* SYMBOLICALLY — not just check values, but REASON about the system. *)

(* Symbolic range: what values satisfy ALL constraints simultaneously? *)
symbolicRange[constraints_List] := Module[
  {vars, ranges, intersection},
  vars = Table[Unique["x"], {Length[constraints]}];
  ranges = MapThread[Function[{c, v}, c[[1]] <= v <= c[[2]]], {constraints, vars}];
  (* All constraints on the SAME variable: *)
  intersection = Simplify[And @@ ranges];
  intersection
]

(* Detect contradictions: is any constraint unsatisfiable? *)
findContradictions[constraints_List] := Module[
  {pairs},
  pairs = Subsets[constraints, {2}];
  Select[pairs, 
    Simplify[Not[#[[1,2]] >= #[[2,1]] || #[[2,2]] >= #[[1,1]]]] &
  ]
]

(* Overlap analysis: which constraints share valid ranges? *)
constraintOverlap[c1_List, c2_List] := Module[
  {lo1, hi1, lo2, hi2, overlapLo, overlapHi},
  {lo1, hi1} = {c1[[1]], c1[[2]]};
  {lo2, hi2} = {c2[[1]], c2[[2]]};
  overlapLo = Max[lo1, lo2];
  overlapHi = Min[hi1, hi2];
  If[overlapLo <= overlapHi,
    {overlapLo, overlapHi},
    {}
  ]
]

(* ══ Industry Presets ══════════════════════════════════════════════ *)

aviation = {
  {-55, 70, "cabin_temp_C"},
  {75, 101, "cabin_pressure_kPa"},
  {0, 100, "fuel_flow_pct"},
  {60, 100, "hydraulic_pct"}
};

automotive = {
  {-40, 60, "battery_temp_C"},
  {0, 100, "soc_pct"},
  {0, 100, "charge_rate_pct"},
  {20, 80, "cabin_temp_C"}
};

nuclear = {
  {0, 110, "neutron_flux_pct"},
  {0, 65, "core_temp_C_x10"},
  {72, 100, "pressurizer_pct"},
  {0, 100, "coolant_flow_pct"}
};

medical = {
  {36, 38, "body_temp_C"},
  {60, 100, "heart_rate_bpm"},
  {95, 100, "spo2_pct"},
  {80, 120, "bp_systolic_mmHg"}
};

maritime = {
  {-2, 35, "sea_temp_C"},
  {50, 100, "hull_integrity_pct"},
  {0, 50, "wave_height_m"},
  {0, 80, "wind_speed_kn"}
};

energy = {
  {49, 51, "grid_freq_Hz_x10"},
  {95, 105, "voltage_pct"},
  {0, 80, "transformer_temp_C"},
  {0, 100, "line_load_pct"}
};

railway = {
  {0, 100, "speed_pct"},
  {0, 100, "brake_pressure_pct"},
  {0, 1, "door_interlock"},
  {0, 80, "track_temp_C"}
};

robotics = {
  {-100, 100, "joint_torque_pct"},
  {0, 100, "speed_pct"},
  {0, 100, "force_pct"},
  {-127, 127, "position_mm"}
};

space = {
  {-40, 50, "temp_C"},
  {0, 100, "solar_panel_pct"},
  {0, 100, "propellant_pct"},
  {0, 100, "battery_pct"}
};

underwater = {
  {0, 100, "depth_pct"},
  {0, 100, "battery_pct"},
  {-5, 35, "water_temp_C"},
  {0, 100, "thruster_pct"}
};

(* ══ Demo ══════════════════════════════════════════════════════════ *)

Print["═══ FLUX Constraint Engine — Wolfram (Symbolic Computation) ═══"];
Print[];

Print["  Aviation val=60:  ", fluxCheck[aviation, 60]["severityName"]];
Print["  Aviation val=25:  ", fluxCheck[aviation, 25]["severityName"]];
Print["  Nuclear val=127:  ", fluxCheck[nuclear, 127]["severityName"]];
Print[];

(* SYMBOLIC analysis — unique to Wolfram *)
Print["  Constraint overlap (cabin_temp vs hydraulic): "];
Print["    ", constraintOverlap[aviation[[1]], aviation[[4]]]];
Print[];

Print["  Symbolic range for body_temp_C: "];
Print["    Simplify[36 <= x <= 38] = ", Simplify[36 <= x <= 38]];
Print[];

(* Simplify a constraint expression *)
Print["  Simplify[-55 <= 60 <= 70] = ", Simplify[-55 <= 60 <= 70]];
Print["    (* True — constraint satisfied *)"];
Print["  Simplify[75 <= 60 <= 101] = ", Simplify[75 <= 60 <= 101]];
Print["    (* False — constraint violated *)"];

(* Wolfram teaches us that constraint checking is SYMBOLIC REDUCTION.
   Simplify[constraint] tells you everything:
   - True → trivially satisfied
   - False → impossible (contradiction)
   - An expression → the conditions for satisfaction
   
   Most languages CHECK constraints. Wolfram UNDERSTANDS them. *)
