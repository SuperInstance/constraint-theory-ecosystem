# flux-check

Production CLI for **FLUX constraint theory** — zero-overhead bounds validation against domain-specific presets.

## Installation

```bash
cd constraint-theory-ecosystem/src/rust
cargo build --release
# Binary at target/release/flux-check
```

## Usage

### Check a single value against a preset

```bash
flux-check --preset automotive_can --value 3000
```

Output:
```
━━━ FLUX Constraint Check ━━━
Value:   3000
Mask:    01000000 (decimal: 64)
Result:  ✗ FAIL
Severity: Caution

Constraints:
  [✓]   0 [    0.00,  8000.00]  engine_rpm
  [✗]   1 [    0.00,   300.00]  vehicle_speed_kmh
  [✓]   2 [  -40.00,   150.00]  coolant_temp_c
  ...
```

### Custom bounds

```bash
flux-check --bounds "-40,150" --bounds "0,8000" --value 3500
```

### Batch CSV checking

```bash
flux-check --preset aviation_adsb --csv sensor_data.csv --column altitude
```

### Benchmark a preset

```bash
flux-check --preset automotive_can --benchmark --iterations 1000000
```

### Compile to target language

```bash
# C output
flux-check --preset medical_fhir --compile c --output medical_check.c

# WebAssembly (WAT)
flux-check --preset automotive_can --compile wasm --output check.wat

# Rust
flux-check --preset automotive_can --compile rust
```

### Proof certificates

```bash
# Generate
flux-check --preset automotive_can --value 3000 --proof --output proof.json

# Verify
flux-check --verify proof.json
```

## Available Presets

| Preset | Domain | Constraints |
|--------|--------|:-----------:|
| `automotive_can` | Vehicle CAN bus | 8 |
| `aviation_adsb` | ADS-B telemetry | 8 |
| `medical_fhir` | Health data (FHIR) | 8 |
| `energy_scada` | Power grid SCADA | 8 |
| `industrial_plc` | Industrial PLC sensors | 8 |
| `iot_environmental` | Environmental sensors | 8 |
| `robotics_ros` | ROS joint/sensor data | 8 |
| `telecom_5g` | 5G network signals | 8 |
| `marine_nmea` | Marine NMEA data | 8 |
| `satellite_telemetry` | Satellite telemetry | 8 |

Run `flux-check` with no arguments to list all presets with bounds.

## Architecture

The checker implements the same hot path as the C `flux_check_exact()` function:
- Bitmask construction via tight comparison loop
- NaN violates all constraints
- Boundary values (lo, hi) are inclusive passes
- Up to 8 constraints per check (matches FLUX_EXACT_MAX_CONSTRAINTS)

## Proof Certificate Format

JSON with full reproducibility:

```json
{
  "version": "1.0.0",
  "preset": "automotive_can",
  "constraints": [
    { "index": 0, "lo": 0.0, "hi": 8000.0, "passed": true },
    ...
  ],
  "value": 3000.0,
  "mask": 2,
  "mask_binary": "00000010",
  "passed": false,
  "severity": "Caution",
  "timestamp": "2026-05-19T20:30:00Z",
  "tool": "flux-check 0.1.0"
}
```

Verification rebuilds the checker from the constraint definitions and re-checks the value, confirming the mask matches.

## Performance

On the Rust hot path (LLVM `-C opt-level=3`), expect **500M+ checks/sec** on modern x86_64 — matching the C implementation. The loop is auto-vectorization friendly with no branches beyond the comparisons.

## License

Part of the SuperInstance constraint-theory-ecosystem.
