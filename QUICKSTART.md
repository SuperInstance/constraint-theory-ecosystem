# Quickstart Tutorial — FLUX Constraint Engine

*15 minutes to your first constraint check. No installation required.*

---

## Option 1: Browser (Zero Install)

Open `tools/playground.html` in any browser. You'll see:

1. **Sensor Input** — Enter a value (-127 to 127)
2. **Constraints** — Set bounds for up to 8 constraints
3. **Evaluate** — Get pass/fail with severity and error mask

Try these experiments:
- Set constraint to [0, 100], enter value 50 → **PASS**
- Same constraint, enter 150 → **FAIL** (value saturates to 127, still > 100)
- Load the Aviation preset, enter -60 → **CRITICAL** (all 4 constraints violated)

## Option 2: Python (pip install)

```python
# Copy src/python/flux_constraint.py to your project
from flux_constraint import FluxConstraint, Severity

# Define constraints for a battery management system
fc = FluxConstraint([
    {"lo": -20, "hi": 60, "name": "cell_temp_C"},
    {"lo": 0,   "hi": 100, "name": "soc_pct"},
    {"lo": 0,   "hi": 100, "name": "charge_rate_pct"},
    {"lo": 20,  "hi": 80, "name": "cabin_temp_C"},
])

# Check a value
result = fc.check(70)  # 70°C battery temperature
print(result.severity)      # Severity.CAUTION
print(result.error_mask)    # 0x01 (first constraint: 70 > 60)
print(result.passed)        # False

# Use a preset
fc = FluxConstraint.from_preset("aviation")
result = fc.check(25)
print(result.passed)        # Depends on preset constraints

# Batch check
results, stats = fc.check_batch([-60, 0, 25, 70, 90, 127])
print(stats)  # {'pass': N, 'caution': N, 'warning': N, 'critical': N}

# Benchmark
bench = fc.benchmark()
print(f"{bench['rate_M']:.1f}M checks/sec")
```

## Option 3: JavaScript (Node.js or Browser)

```javascript
// Copy src/js/flux-constraint.js to your project
const { FluxConstraint } = require('./flux-constraint.js')

const fc = new FluxConstraint([
    { lo: -20, hi: 60, name: 'cell_temp_C' },
    { lo: 0, hi: 100, name: 'soc_pct' },
])

const result = fc.check(70)
console.log(result.severity)    // 1 = CAUTION
console.log(result.passed)      // false
console.log(result.details)     // [{name, lo, hi, passed}, ...]

// Use a preset
const medical = FluxConstraint.fromPreset('medical')
const r = medical.check(37)
console.log(r.passed)           // true (body temp in range)

// Benchmark
const bench = medical.benchmark()
console.log(`${(bench.rate / 1e6).toFixed(1)}M checks/sec`)
```

## Option 4: PHP

```php
<?php
// Copy src/php/FluxConstraint.php to your project
require_once 'FluxConstraint.php';

use FluxConstraint;

$fc = new FluxConstraint([
    ['lo' => -20, 'hi' => 60, 'name' => 'cell_temp_C'],
    ['lo' => 0, 'hi' => 100, 'name' => 'soc_pct'],
]);

$result = $fc->check(70);
echo $result->severity;    // 1 = CAUTION
echo $result->passed;      // false
echo $result->error_mask;  // 0x01
```

## Option 5: Rust

```rust
// Copy src/rust/flux_constraint.rs to your project
// See src/rust/flux_constraint.rs for full API

use flux_constraint::{FluxChecker, Constraint};

let checker = FluxChecker::new(vec![
    Constraint { lo: -20, hi: 60, name: "cell_temp_C" },
    Constraint { lo: 0, hi: 100, name: "soc_pct" },
]).unwrap();

let result = checker.check(70);
assert_eq!(result.severity, 1); // CAUTION
```

## Option 6: C (Embedded ARM)

```c
// Copy src/embedded/flux_embedded.h to your project
#include "flux_embedded.h"

FluxVM vm;
flux_vm_init(&vm);

// Check: value=70, lo=-20, hi=60
uint8_t bytecode[] = {
    FLUX_CONSTRAINT_ID, 0,
    FLUX_PUSH, 70,           // value
    FLUX_PUSH, (uint8_t)(int8_t)(-20),  // lo
    FLUX_PUSH, 60,           // hi
    FLUX_RANGE_CHECK,
    FLUX_HALT
};

FluxResult result = {0};
FluxError err = flux_execute(&vm, bytecode, sizeof(bytecode), &result);
// result.error_mask = 0x01 (violated)
// result.severity = 1 (CAUTION)
```

## Option 7: CUDA (GPU)

```cuda
// Copy src/cuda/flux_production_v2.cu to your project
// See experiments/ for full benchmark examples

// 62.2 billion constraint checks per second
// 60 million differential inputs, zero mismatches
```

---

## Industry Presets Available

| Preset | Language | Constraints |
|--------|----------|-------------|
| Aviation | DO-178C | Cabin temp, pressure, fuel flow, hydraulic |
| Automotive | ISO 26262 | Battery temp, SOC, charge rate, cabin |
| Maritime | SOLAS | Sea temp, hull integrity, waves, wind |
| Medical | IEC 62304 | Body temp, heart rate, SpO2, BP |
| Energy | IEC 61850 | Grid freq, voltage, transformer temp, load |
| Nuclear | NRC | Neutron flux, core temp, pressurizer, coolant |
| Railway | EN 50128 | Speed, brakes, door interlock, track temp |
| Robotics | ISO 10218 | Torque, speed, force, position |
| Space | ECSS | Temperature, solar, propellant, battery |
| Underwater | DNVT | Depth, battery, water temp, thruster |

---

## Next Steps

1. Read [Physical Engineer's Guide](docs/physical-engineers-guide.md) for the theory
2. Try the [Browser Playground](tools/playground.html) for hands-on
3. Read [Industry Examples](docs/examples.md) for your domain
4. Deploy the [REST API](tools/rest-api-guide.md) for production

---

*Pick a language. Check a constraint. Ship it.*
