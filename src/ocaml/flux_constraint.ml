// FLUX Constraint Engine — OCaml 5
// Pure INT8 saturated constraint checking. Zero dependencies.

let int8_min = -127
let int8_max = 127

let saturate v = max int8_min (min int8_max v)

type severity = Pass | Caution | Warning | Critical

type constraint_def = { lo: int; hi: int; name: string }

type flux_result = {
  error_mask: int;
  severity: severity;
  violated_lo: int;
  violated_hi: int;
  violated_count: int;
  passed: bool;
}

let check constraints value =
  let val = saturate value in
  let error_mask, violated_lo, violated_hi, violated_count =
    List.fold_left (fun (em, vlo, vhi, vc) (i, c) ->
      let lo = saturate c.lo and hi = saturate c.hi in
      let lo_fail = val < lo and hi_fail = val > hi in
      let em' = if lo_fail || hi_fail then em lor (1 lsl i) else em in
      let vlo' = if lo_fail then vlo lor (1 lsl i) else vlo in
      let vhi' = if hi_fail then vhi lor (1 lsl i) else vhi in
      let vc' = if lo_fail || hi_fail then vc + 1 else vc in
      (em', vlo', vhi', vc')
    ) (0, 0, 0, 0) (List.mapi (fun i c -> (i, c)) constraints)
  in
  let nc = List.length constraints in
  let sev = if violated_count = 0 then Pass
            else if violated_count <= nc / 4 then Caution
            else if violated_count <= nc / 2 then Warning
            else Critical in
  { error_mask; severity = sev; violated_lo; violated_hi; violated_count; passed = sev = Pass }

let check_batch constraints values =
  let results = List.map (check constraints) values in
  let count_sev s = List.length (List.filter (fun r -> r.severity = s) results) in
  let stats = [
    ("pass", count_sev Pass); ("caution", count_sev Caution);
    ("warning", count_sev Warning); ("critical", count_sev Critical)
  ] in
  (results, stats)

let benchmark constraints iterations =
  let t0 = Sys.time () in
  for _ = 1 to iterations do
    ignore (check constraints 50)
  done;
  let elapsed = Sys.time () -. t0 in
  (float iterations *. float (List.length constraints) /. elapsed, elapsed *. 1000.0)

let presets = [
  ("aviation", [
    {lo = -55; hi = 70; name = "cabin_temp_C"};
    {lo = 75; hi = 101; name = "cabin_pressure_kPa"};
    {lo = 0; hi = 100; name = "fuel_flow_pct"};
    {lo = 60; hi = 100; name = "hydraulic_pct"};
  ]);
  ("medical", [
    {lo = 36; hi = 38; name = "body_temp_C"};
    {lo = 60; hi = 100; name = "heart_rate_bpm"};
    {lo = 95; hi = 100; name = "spo2_pct"};
    {lo = 80; hi = 120; name = "bp_systolic_mmHg"};
  ]);
  ("maritime", [
    {lo = -2; hi = 35; name = "sea_temp_C"};
    {lo = 50; hi = 100; name = "hull_integrity_pct"};
    {lo = 0; hi = 50; name = "wave_height_m"};
    {lo = 0; hi = 80; name = "wind_speed_kn"};
  ]);
  ("automotive", [
    {lo = -40; hi = 60; name = "battery_temp_C"};
    {lo = 0; hi = 100; name = "soc_pct"};
    {lo = 0; hi = 100; name = "charge_rate_pct"};
    {lo = 20; hi = 80; name = "cabin_temp_C"};
  ]);
  ("energy", [
    {lo = 49; hi = 51; name = "grid_freq_Hz_x10"};
    {lo = 95; hi = 105; name = "voltage_pct"};
    {lo = 0; hi = 80; name = "transformer_temp_C"};
    {lo = 0; hi = 100; name = "line_load_pct"};
  ]);
]

let from_preset name =
  match List.assoc_opt name presets with
  | Some cs -> cs
  | None -> failwith (Printf.sprintf "Unknown preset: %s" name)

(* Self-test *)
let () =
  Printf.printf "FLUX Constraint Engine — OCaml\n";
  Printf.printf "===============================\n";
  assert (saturate (-128) = -127);
  assert (saturate 128 = 127);
  Printf.printf "  saturate: OK\n";
  let fc = [{lo = 0; hi = 100; name = "test"}] in
  assert (check fc 50).passed;
  assert (not (check fc 150).passed);
  Printf.printf "  check: OK\n";
  let fc4 = [{lo=0;hi=10;name="a"};{lo=0;hi=10;name="b"};{lo=0;hi=10;name="c"};{lo=0;hi=10;name="d"}] in
  let r = check fc4 50 in
  assert (r.severity = Critical && r.violated_count = 4);
  Printf.printf "  severity: OK\n";
  let fc3 = from_preset "aviation" in
  assert (List.length fc3 = 4);
  Printf.printf "  presets: OK\n";
  Printf.printf "  All tests pass\n"
