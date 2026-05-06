// FLUX Constraint Engine — F#
// Pure INT8 saturated constraint checking. Zero dependencies.

module FluxConstraint

let Int8Min, Int8Max = -127, 127

let saturate v = max Int8Min (min Int8Max v)

type Severity = Pass = 0 | Caution = 1 | Warning = 2 | Critical = 3

type ConstraintDef = { Lo: int; Hi: int; Name: string }

type FluxResult = {
    ErrorMask: int
    Severity: Severity
    ViolatedLo: int
    ViolatedHi: int
    ViolatedCount: int
    Passed: bool
}

let check (constraints: ConstraintDef list) (value: int) =
    let val = saturate value
    let mutable errorMask, violatedLo, violatedHi, violatedCount = 0, 0, 0, 0

    constraints |> List.iteri (fun i c ->
        let lo = saturate c.Lo
        let hi = saturate c.Hi
        let loFail = val < lo
        let hiFail = val > hi
        if loFail || hiFail then
            errorMask <- errorMask ||| (1 <<< i)
            violatedCount <- violatedCount + 1
        if loFail then violatedLo <- violatedLo ||| (1 <<< i)
        if hiFail then violatedHi <- violatedHi ||| (1 <<< i)
    )

    let nc = constraints.Length
    let sev =
        if violatedCount = 0 then Severity.Pass
        elif violatedCount <= nc / 4 then Severity.Caution
        elif violatedCount <= nc / 2 then Severity.Warning
        else Severity.Critical

    { ErrorMask = errorMask; Severity = sev; ViolatedLo = violatedLo
      ViolatedHi = violatedHi; ViolatedCount = violatedCount; Passed = sev = Severity.Pass }

let checkBatch constraints values =
    let results = values |> List.map (check constraints)
    let stats = Map [
        "pass", results |> List.filter (fun r -> r.Severity = Severity.Pass) |> List.length
        "caution", results |> List.filter (fun r -> r.Severity = Severity.Caution) |> List.length
        "warning", results |> List.filter (fun r -> r.Severity = Severity.Warning) |> List.length
        "critical", results |> List.filter (fun r -> r.Severity = Severity.Critical) |> List.length
    ]
    results, stats

let benchmark constraints iterations =
    let sw = System.Diagnostics.Stopwatch.StartNew()
    for i = 0 to iterations - 1 do
        check constraints ((i % 254) - 127) |> ignore
    sw.Stop()
    let rate = float iterations * float constraints.Length / sw.Elapsed.TotalSeconds
    rate, sw.Elapsed.TotalMilliseconds

let presets = Map [
    "aviation", [
        { Lo = -55; Hi = 70; Name = "cabin_temp_C" }
        { Lo = 75; Hi = 101; Name = "cabin_pressure_kPa" }
        { Lo = 0; Hi = 100; Name = "fuel_flow_pct" }
        { Lo = 60; Hi = 100; Name = "hydraulic_pct" }
    ]
    "medical", [
        { Lo = 36; Hi = 38; Name = "body_temp_C" }
        { Lo = 60; Hi = 100; Name = "heart_rate_bpm" }
        { Lo = 95; Hi = 100; Name = "spo2_pct" }
        { Lo = 80; Hi = 120; Name = "bp_systolic_mmHg" }
    ]
    "automotive", [
        { Lo = -40; Hi = 60; Name = "battery_temp_C" }
        { Lo = 0; Hi = 100; Name = "soc_pct" }
        { Lo = 0; Hi = 100; Name = "charge_rate_pct" }
        { Lo = 20; Hi = 80; Name = "cabin_temp_C" }
    ]
    "energy", [
        { Lo = 49; Hi = 51; Name = "grid_freq_Hz_x10" }
        { Lo = 95; Hi = 105; Name = "voltage_pct" }
        { Lo = 0; Hi = 80; Name = "transformer_temp_C" }
        { Lo = 0; Hi = 100; Name = "line_load_pct" }
    ]
]

let fromPreset name =
    match presets.TryFind name with
    | Some cs -> cs
    | None -> failwith $"Unknown preset: {name}"

[<EntryPoint>]
let main _ =
    printfn "FLUX Constraint Engine — F#"
    printfn "==========================="

    assert (saturate -128 = -127)
    assert (saturate 128 = 127)
    printfn "  saturate: OK"

    let fc = [{ Lo = 0; Hi = 100; Name = "test" }]
    assert (check fc 50).Passed
    assert not (check fc 150).Passed
    printfn "  check: OK"

    let fc4 = [{Lo=0;Hi=10;Name="a"};{Lo=0;Hi=10;Name="b"};{Lo=0;Hi=10;Name="c"};{Lo=0;Hi=10;Name="d"}]
    let r = check fc4 50
    assert (r.Severity = Severity.Critical && r.ViolatedCount = 4)
    printfn "  severity: OK"

    printfn "  All tests pass"
    0
