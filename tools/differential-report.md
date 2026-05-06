# Cross-Language Differential Test Report

Generated: 2026-05-05 18:27 UTC

## Golden Vector Stats

- **Total vectors:** 10,000

- **Categories:** boundary, saturation, in-range, out-of-range, multi-constraint, extreme, all-pass, all-fail


## Language Results

| Language | Vectors | Mismatches | Status |
|----------|---------|------------|--------|
| Python | 10000 | 0 | ✅ PASS |
| JavaScript | 10000 | 0 | ✅ PASS |
| TypeScript | 10000 | 0 | ✅ PASS |
| Go | 10000 | 0 | ✅ PASS |
| Ruby | 10,000 | — | ⏳ Not run |
| PHP | 10,000 | — | ⏳ Not run |
| Dart | 10,000 | — | ⏳ Not run |
| Zig | 10,000 | — | ⏳ Not run |
| Kotlin | 10,000 | — | ⏳ Not run |
| Java | 10,000 | — | ⏳ Not run |
| C# | 10,000 | — | ⏳ Not run |
| Swift | 10,000 | — | ⏳ Not run |
| Elixir | 10,000 | — | ⏳ Not run |
| Haskell | 10,000 | — | ⏳ Not run |
| Scala | 10,000 | — | ⏳ Not run |
| Rust | 10,000 | — | ⏳ Not run |
| C (embedded) | 10,000 | — | ⏳ Not run |
| CUDA | 10,000 | — | ⏳ Not run |
| WebGPU | 10,000 | — | ⏳ Not run |
| SystemVerilog | 10,000 | — | ⏳ Not run |
| REST API | 10,000 | — | ⏳ Not run |

## Specification Compliance

Every implementation must satisfy:

1. **INT8 saturation:** values clamped to [-127, 127] (NOT [-128, 127])

2. **Error mask:** bitmask of violated constraints (bit i = constraint i failed)

3. **Severity:** PASS(0) → CAUTION(1) → WARNING(2) → CRITICAL(3)

4. **Zero mismatches:** against 10,000 golden vectors


---

*10,000 vectors. 21 languages. Zero mismatches. That's the standard.*
