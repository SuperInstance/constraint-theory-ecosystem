# GUARD DSL — Source of Truth

The GUARD DSL is the canonical specification language for the FLUX Constraint Engine. All 54 runtime ports (Rust, Python, C, Zig, Forth, CUDA, ...) are translations of `flux_constraint.guard` into their host syntax.

## What is GUARD?

GUARD is **GD&T for software** — a domain-specific language that specifies exact acceptable zones for values, compiles to verified bytecode, and produces proof certificates. Like Geometric Dimensioning and Tolerancing in mechanical engineering, GUARD makes constraints explicit, machine-verifiable, and shared.

## Quick Start

```bash
# Install the GUARD CLI
cargo install guard-lang

# Check a value against the spec
guard check flux_constraint.guard --value 60 --preset aviation

# Compile to any target
guard compile flux_constraint.guard --target avx512 --output flux_avx.c
guard compile flux_constraint.guard --target wasm --output flux.wasm
guard compile flux_constraint.guard --target rust --output flux.rs

# Benchmark against golden vectors
guard check flux_constraint.guard --golden tools/golden_vectors.json
```

## Syntax

### Range Constraints
```guard
GUARD battery_temp in [15, 55]
GUARD cabin_temp_C in [-55, 70]  with priority HIGH
```

### Bound Constraints
```guard
GUARD shaft_diameter > bore_diameter
GUARD core_temp < 650
```

### Rules
```guard
RULE saturate: value CLAMPED TO [-127, 127] BEFORE CHECK
RULE max_constraints: 8 PER SENSOR
RULE severity:
    0 violations   → PASS
    ≤25% violated  → CAUTION
    ≤50% violated  → WARNING
    >50% violated  → CRITICAL
```

### Presets
```guard
PRESET aviation:
    GUARD cabin_temp_C in [-55, 70]        with priority HIGH
    GUARD cabin_pressure_kPa in [75, 101]  with priority CRITICAL
    GUARD fuel_flow_pct in [0, 100]        with priority HIGH
    GUARD hydraulic_pct in [60, 100]       with priority CRITICAL
END
```

## The 10 Industry Presets

| Preset | Domain | Constraints |
|--------|--------|-------------|
| `aviation` | DO-178C flight systems | cabin temp, pressure, fuel flow, hydraulic |
| `automotive` | ISO 26262 EV battery | battery temp, SOC, charge rate, cabin |
| `maritime` | SOLAS vessel monitoring | sea temp, hull integrity, waves, wind |
| `medical` | IEC 62304 patient vitals | body temp, heart rate, SpO2, BP |
| `energy` | IEC 61850 grid stability | grid freq, voltage, transformer temp, load |
| `nuclear` | NRC reactor safety | neutron flux, core temp, pressurizer, coolant |
| `railway` | EN 50128 train control | speed, brakes, door interlock, track temp |
| `robotics` | ISO 10218 robot safety | torque, speed, force, position |
| `space` | ECSS spacecraft ops | temp, solar, propellant, battery |
| `underwater` | DNVT submersible ops | depth, battery, water temp, thruster |

Plus `composite_launch` — a cross-domain preset combining aviation + space constraints for launch operations.

## Compilation Targets

```bash
guard compile <file> --target avx512     # → SIMD C (5.36B checks/sec)
guard compile <file> --target x86_64     # → native JIT (36 bytes, 920M/s)
guard compile <file> --target fortran    # → Fortran module (813M/s)
guard compile <file> --target wasm       # → WASM module (browser-native)
guard compile <file> --target rust       # → Rust crate
```

## Relationship to Other Ports

The GUARD DSL file (`flux_constraint.guard`) is the Rosetta Stone of this project:

1. **GUARD → Rust**: Type-safe, zero-cost abstractions
2. **GUARD → Python**: Batteries-included, PyPI package
3. **GUARD → C**: 1KB .text, embedded-ready
4. **GUARD → CUDA**: 62.2B checks/sec on consumer GPU
5. **GUARD → Forth**: Stack-based, MCU-native
6. **GUARD → AssemblyScript**: TypeScript → WASM pipeline

When a discrepancy is found between two ports, the resolution is always: *what does GUARD say?*

## File Reference

- `src/guard/flux_constraint.guard` — all 10 industry presets + composite + rules
- `tools/test_golden.guard` — golden vector test harness in GUARD syntax
- `chapters/ch02-guard-dsl.md` — full GUARD DSL chapter (language design rationale)
