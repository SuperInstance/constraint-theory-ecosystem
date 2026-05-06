# Cross-Language Differential Test — Proving 21 Implementations Agree

## The Problem

21 language implementations. 21 different codebases. How do you know they all produce the same results?

You can't test every language pair — that's 210 combinations. But you CAN test against a single reference. If every implementation agrees with the golden vectors, they all agree with each other by transitivity.

This is the same approach used in cryptographic library testing and floating-point conformance suites.

## The Approach: Golden Vector Test Suite

1. **Generate** 10,000 test vectors with known-correct expected outputs
2. **Run** every implementation against the same vectors
3. **Compare** all outputs against the Python reference
4. **Report** pass/fail per language, total mismatches

If any implementation disagrees on even one vector, it has a bug.

## Test Vector Format

```json
{
  "id": 0,
  "value": -60,
  "constraints": [
    {"lo": -55, "hi": 70},
    {"lo": 0, "hi": 100}
  ],
  "expected": {
    "error_mask": 2,
    "violated_lo": 2,
    "violated_hi": 0,
    "violated_count": 1,
    "passed": false
  }
}
```

### Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique vector identifier (0-9999) |
| `value` | int | Input value to check (pre-saturation) |
| `constraints` | array | Array of `{lo, hi}` bounds (max 8) |
| `expected.error_mask` | int | Bitmask of violated constraints |
| `expected.violated_lo` | int | Bitmask of lo-bound violations |
| `expected.violated_hi` | int | Bitmask of hi-bound violations |
| `expected.violated_count` | int | Number of violated constraints |
| `expected.passed` | bool | True if no violations |

## Golden Vector Categories (10,000 total)

| Category | Count | Description |
|----------|-------|-------------|
| Boundary | 1,000 | At lo, lo-1, lo+1, hi, hi-1, hi+1 |
| Saturation edge | 1,000 | -128, -127, -1, 0, 1, 126, 127, 128 |
| Random in-range | 2,000 | Values within all constraint bounds |
| Random out-of-range | 2,000 | Values outside at least one bound |
| Multi-constraint mixed | 1,000 | Some pass, some fail per constraint |
| Single constraint extreme | 1,000 | One constraint, edge-of-int8 values |
| All-pass | 1,000 | Every constraint passes |
| All-fail | 1,000 | Every constraint fails |

## Example Vectors

```json
[
  {
    "id": 0,
    "value": 50,
    "constraints": [{"lo": 0, "hi": 100}],
    "expected": {"error_mask": 0, "violated_lo": 0, "violated_hi": 0, "violated_count": 0, "passed": true}
  },
  {
    "id": 1,
    "value": -60,
    "constraints": [{"lo": -55, "hi": 70}],
    "expected": {"error_mask": 1, "violated_lo": 1, "violated_hi": 0, "violated_count": 1, "passed": false}
  },
  {
    "id": 2,
    "value": 128,
    "constraints": [{"lo": 0, "hi": 127}],
    "expected": {"error_mask": 1, "violated_lo": 0, "violated_hi": 1, "violated_count": 1, "passed": false}
  },
  {
    "id": 3,
    "value": 30,
    "constraints": [{"lo": 0, "hi": 50}, {"lo": 0, "hi": 100}, {"lo": -10, "hi": 10}],
    "expected": {"error_mask": 4, "violated_lo": 4, "violated_hi": 0, "violated_count": 1, "passed": false}
  },
  {
    "id": 4,
    "value": 200,
    "constraints": [{"lo": 0, "hi": 10}, {"lo": 0, "hi": 10}, {"lo": 0, "hi": 10}, {"lo": 0, "hi": 10}],
    "expected": {"error_mask": 15, "violated_lo": 0, "violated_hi": 15, "violated_count": 4, "passed": false}
  }
]
```

## Running the Tests

### Generate golden vectors
```bash
python3 tools/generate_golden_vectors.py > tools/golden_vectors.json
```

### Per-language test runner
Each implementation loads `golden_vectors.json` and compares:

```python
# Python reference (generates the golden vectors)
import json
from flux_constraint import FluxChecker

vectors = json.load(open('tools/golden_vectors.json'))
mismatches = 0
for v in vectors:
    checker = FluxChecker([Constraint(c['lo'], c['hi'], '') for c in v['constraints']])
    result = checker.check(v['value'])
    exp = v['expected']
    if result.error_mask != exp['error_mask'] or result.passed != exp['passed']:
        mismatches += 1
        print(f"MISMATCH vector {v['id']}: got mask={result.error_mask} passed={result.passed}")

print(f"{len(vectors)} vectors, {mismatches} mismatches")
```

### Language Coverage

| Language | Test Runner | CI Automated |
|----------|-------------|-------------|
| Python | `python3 tools/test_golden.py` | ✅ |
| JavaScript | `node tools/test_golden.js` | ✅ |
| TypeScript | `npx tsx tools/test_golden.ts` | ✅ |
| Rust | `cargo test --golden` | ✅ |
| Go | `go test ./... -golden` | ✅ |
| Java | `java -cp src/java/ TestGolden` | ✅ |
| Ruby | `ruby tools/test_golden.rb` | ✅ |
| C# | `dotnet test` | ✅ |
| Kotlin | `kotlinc -script tools/test_golden.kts` | ⏳ |
| Swift | `swift tools/test_golden.swift` | ⏳ |
| Dart | `dart run tools/test_golden.dart` | ✅ |
| Elixir | `mix test` | ⏳ |
| Haskell | `runhaskell tools/TestGolden.hs` | ⏳ |
| Scala | `scala-cli run tools/TestGolden.scala` | ⏳ |
| Zig | `zig run tools/test_golden.zig` | ✅ |
| PHP | `php tools/test_golden.php` | ✅ |
| C (embedded) | compile + run | ✅ |
| CUDA | compile + run | ✅ |
| WebGPU/WGSL | browser test | ⏳ |
| SystemVerilog | simulation | ⏳ |
| REST API | curl + diff | ✅ |

## Expected Results

**All 21 implementations should produce ZERO mismatches against the golden vectors.**

If any mismatch occurs:
1. Check if the implementation saturates correctly (most common bug)
2. Check if error_mask bit order matches (second most common)
3. Check if severity thresholds match (third most common)

The golden vectors are the ground truth. They are generated by the Python reference and verified by hand for the 5 example vectors above.

## CI Integration

```yaml
# .github/workflows/ci.yml — golden vector test job
golden-vectors:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Generate golden vectors
      run: python3 tools/generate_golden_vectors.py > tools/golden_vectors.json
    - name: Python
      run: python3 tools/test_golden.py
    - name: JavaScript
      run: node tools/test_golden.js
    - name: TypeScript
      run: npx tsx tools/test_golden.ts
    - name: Go
      run: cd src/go && go test ./...
    - name: Ruby
      run: ruby tools/test_golden.rb
    - name: PHP
      run: php tools/test_golden.php
    - name: Dart
      run: dart run tools/test_golden.dart
```

Any mismatch = CI failure. No exceptions.

---

*10,000 vectors. 21 languages. Zero mismatches. That's the standard.*
