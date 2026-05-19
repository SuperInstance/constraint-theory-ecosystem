# FLUX Constraint Engine — Real-World Application Benchmarks

Generated: 2026-05-19 10:53:20

## Test Environments

Each test ports a real-world constraint checking pattern to the FLUX polylanguage system.
FLUX uses INT8 saturated arithmetic [-127, 127] with automatic scaling from real-world ranges.

## Summary Table

| Domain | Signals | Required Rate | FLUX Throughput | Headroom | p99 Latency | False Positive Rate | False Negative Rate |
|--------|---------|---------------|-----------------|----------|-------------|--------------------|--------------------|
| Aviation (ADS-B) | 5 | 1,000,000/s | 1,044,897/s | 1.0x | 2.58 μs | 0.0000% | 0.0000% |
| Medical (FHIR) | 8 | 500,000/s | 2,132,696/s | 4.3x | 0.81 μs | 0.0000% | 5.4795% |
| Financial (FIX) | 5 | 1,000,000/s | 2,619,247/s | 2.6x | 0.76 μs | 0.0000% | 0.2869% |
| Energy (SCADA) | 6 | 18,000,000/s | 2,353,655/s | 0.1x | 0.50 μs | 0.0000% | 0.0000% |
| IoT (MQTT) | 6 | 60,000/s | 2,763,350/s | 46.1x | 1.73 μs | 0.0000% | 1.8817% |
| Automotive (CAN) | 8 | 80,000/s | 2,587,889/s | 32.3x | 1.05 μs | 0.0000% | 0.0000% |

## Detailed Results

### Aviation (ADS-B)

- **Total checks:** 5,000
- **FLUX throughput:** 1,044,897 checks/sec
- **Naive throughput:** 16,832,520 checks/sec
- **Headroom:** 1.0x required rate
- **p50 latency:** 0.46 μs
- **p95 latency:** 1.23 μs
- **p99 latency:** 2.58 μs
- **False positives:** 0 (0.0000%)
- **False negatives:** 0 (0.0000%)
- **Accuracy:** 100.0000%
- **True violations:** 68
- **Detected violations:** 68

### Medical (FHIR)

- **Total checks:** 80,000
- **FLUX throughput:** 2,132,696 checks/sec
- **Naive throughput:** 10,068,430 checks/sec
- **Headroom:** 4.3x required rate
- **p50 latency:** 0.35 μs
- **p95 latency:** 0.54 μs
- **p99 latency:** 0.81 μs
- **False positives:** 0 (0.0000%)
- **False negatives:** 44 (5.4795%)
- **Accuracy:** 99.9450%
- **True violations:** 803
- **Detected violations:** 759

### Financial (FIX)

- **Total checks:** 500,000
- **FLUX throughput:** 2,619,247 checks/sec
- **Naive throughput:** 15,084,287 checks/sec
- **Headroom:** 2.6x required rate
- **p50 latency:** 0.36 μs
- **p95 latency:** 0.41 μs
- **p99 latency:** 0.76 μs
- **False positives:** 0 (0.0000%)
- **False negatives:** 125 (0.2869%)
- **Accuracy:** 99.9750%
- **True violations:** 43571
- **Detected violations:** 43446

### Energy (SCADA)

- **Total checks:** 300,000
- **FLUX throughput:** 2,353,655 checks/sec
- **Naive throughput:** 13,157,953 checks/sec
- **Headroom:** 0.1x required rate
- **p50 latency:** 0.35 μs
- **p95 latency:** 0.39 μs
- **p99 latency:** 0.50 μs
- **False positives:** 0 (0.0000%)
- **False negatives:** 0 (0.0000%)
- **Accuracy:** 100.0000%
- **True violations:** 251
- **Detected violations:** 251

### IoT (MQTT)

- **Total checks:** 60,000
- **FLUX throughput:** 2,763,350 checks/sec
- **Naive throughput:** 16,086,925 checks/sec
- **Headroom:** 46.1x required rate
- **p50 latency:** 0.44 μs
- **p95 latency:** 1.16 μs
- **p99 latency:** 1.73 μs
- **False positives:** 0 (0.0000%)
- **False negatives:** 14 (1.8817%)
- **Accuracy:** 99.9767%
- **True violations:** 744
- **Detected violations:** 730

### Automotive (CAN)

- **Total checks:** 80,000
- **FLUX throughput:** 2,587,889 checks/sec
- **Naive throughput:** 14,147,773 checks/sec
- **Headroom:** 32.3x required rate
- **p50 latency:** 0.36 μs
- **p95 latency:** 0.48 μs
- **p99 latency:** 1.05 μs
- **False positives:** 0 (0.0000%)
- **False negatives:** 0 (0.0000%)
- **Accuracy:** 100.0000%
- **True violations:** 32
- **Detected violations:** 32

## Methodology

1. **Scaling:** Real-world ranges mapped to INT8 [-127, 127] via linear interpolation
2. **Data generation:** Gaussian distributions centered on typical operating points
3. **Anomaly injection:** Percentage-based injection of out-of-range values
4. **Comparison:** FLUX results compared against naive `lo <= val <= hi` Python checks
5. **Latency:** Measured via `perf_counter_ns()` with percentile reporting
6. **Throughput:** Total checks / wall-clock time for the full batch
7. **Accuracy:** (TP + TN) / total, where ground truth is naive Python range check

## Notes

- FLUX INT8 quantization introduces quantization error near constraint boundaries
- False positives occur when a real value barely passes but quantizes to a failing INT8 value
- False negatives occur when a real value barely fails but quantizes to a passing INT8 value
- The SCADA frequency constraint (59.95-60.05 Hz) is the most challenging for INT8 quantization
- Throughput numbers are single-threaded Python; production Rust/C implementations would be 10-100x faster
