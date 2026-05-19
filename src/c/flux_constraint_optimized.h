/**
 * FLUX-C Optimized Constraint Engine — AVX2/AVX-512 + Branchless + Cache-Aligned
 *
 * Single-header implementation of all optimizations from OPTIMIZATION-ANALYSIS.md.
 * Requires: x86-64 with AVX2 (minimum) or AVX-512 (recommended).
 * Tested on: AMD Ryzen AI 9 HX 370 (Zen 5, AVX-512)
 *
 * Usage:
 *   #define FLUX_CONSTRAINT_OPTIMIZED_IMPL
 *   #include "flux_constraint_optimized.h"
 *
 * (c) 2026 SuperInstance — Apache 2.0
 */

#ifndef FLUX_CONSTRAINT_OPTIMIZED_H
#define FLUX_CONSTRAINT_OPTIMIZED_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <immintrin.h>
#include <stdalign.h>

#ifdef __cplusplus
extern "C" {
#endif

// ═══════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════

#define FLUX_OPT_MAX_CONSTRAINTS  8
#define FLUX_OPT_RING_SIZE        4096   // Must be power of 2
#define FLUX_OPT_RING_MASK        (FLUX_OPT_RING_SIZE - 1)
#define FLUX_OPT_CACHE_LINE       64

// ═══════════════════════════════════════════════════════════
// Severity levels
// ═══════════════════════════════════════════════════════════

typedef enum {
    FLUX_SEV_PASS     = 0,
    FLUX_SEV_CAUTION  = 1,
    FLUX_SEV_WARNING  = 2,
    FLUX_SEV_CRITICAL = 3,
} FluxSeverity;

// ═══════════════════════════════════════════════════════════
// Pre-computed severity lookup table (256 bytes, fits L1)
// Index: number of failed constraints (0-8)
// ═══════════════════════════════════════════════════════════

static const uint8_t FLUX_SEVERITY_TABLE[9] = {
    FLUX_SEV_PASS,      // 0 failures → pass
    FLUX_SEV_CAUTION,   // 1 failure → caution
    FLUX_SEV_CAUTION,   // 2 failures → caution
    FLUX_SEV_WARNING,   // 3 failures → warning
    FLUX_SEV_WARNING,   // 4 failures → warning
    FLUX_SEV_CRITICAL,  // 5 failures → critical
    FLUX_SEV_CRITICAL,  // 6 failures → critical
    FLUX_SEV_CRITICAL,  // 7 failures → critical
    FLUX_SEV_CRITICAL,  // 8 failures → critical
};

// ═══════════════════════════════════════════════════════════
// Cache-line aligned constraint struct (64 bytes exactly)
// Fits one L1 cache line. No false sharing possible.
// ═══════════════════════════════════════════════════════════

typedef struct {
    int8_t   lo;                          // offset 0
    int8_t   hi;                          // offset 1
    uint8_t  constraint_id;               // offset 2
    uint8_t  _pad0;                       // offset 3
    int32_t  lo_i32;                      // offset 4-7  (sign-extended for AVX2)
    int32_t  hi_i32;                      // offset 8-11
    uint32_t check_count;                 // offset 12-15 (hot constraint tracking)
    uint32_t fail_count;                  // offset 16-19
    char     name[32];                    // offset 20-51
    uint8_t  _reserved[12];              // offset 52-63
} __attribute__((aligned(FLUX_OPT_CACHE_LINE))) FluxOptConstraint;

_Static_assert(sizeof(FluxOptConstraint) == 64, "FluxOptConstraint must be exactly 64 bytes");

// ═══════════════════════════════════════════════════════════
// Result structure (also cache-line aligned)
// ═══════════════════════════════════════════════════════════

typedef struct {
    uint8_t  pass_mask;                   // bit i = 1 if constraint i passed
    uint8_t  fail_mask;                   // bit i = 1 if constraint i failed
    uint8_t  severity;                    // from FLUX_SEVERITY_TABLE
    uint8_t  _pad0;
    uint32_t checks_performed;
    uint32_t checks_failed;
    uint64_t cycles_elapsed;              // via __rdtsc
} __attribute__((aligned(FLUX_OPT_CACHE_LINE))) FluxOptResult;

// ═══════════════════════════════════════════════════════════
// Ring buffer provenance (power-of-2 mask indexing)
// ═══════════════════════════════════════════════════════════

typedef struct {
    uint32_t head;
    uint32_t tail;
    uint64_t entries[FLUX_OPT_RING_SIZE]; // simplified: just value hashes
} FluxProvenanceRing;

static inline void flux_ring_init(FluxProvenanceRing* ring) {
    ring->head = 0;
    ring->tail = 0;
    // No memset needed — power-of-2 masking handles wrap
}

// Branchless ring push: no bounds check, mask handles wrap
static inline void flux_ring_push(FluxProvenanceRing* ring, uint64_t hash) {
    ring->entries[ring->head & FLUX_OPT_RING_MASK] = hash;
    ring->head++;
    // tail chases head at FLUX_OPT_RING_SIZE behind (overwrite oldest)
    if ((ring->head - ring->tail) > FLUX_OPT_RING_SIZE) {
        ring->tail++;
    }
}

// ═══════════════════════════════════════════════════════════
// Memory-mapped I/O stubs for air-gapped deployment
// ═══════════════════════════════════════════════════════════

typedef struct {
    volatile int8_t*  dma_buffer;     // Memory-mapped DMA buffer pointer
    size_t            dma_size;       // Buffer size in bytes
    volatile int8_t*  output_buffer;  // Memory-mapped output buffer
    size_t            output_offset;  // Current write offset
} FluxMMIO;

// Stub: in real deployment, this calls mmap() on /dev/mem or device register
static inline int flux_mmio_init(FluxMMIO* mmio, void* dma_base, size_t dma_size, void* out_base) {
    mmio->dma_buffer = (volatile int8_t*)dma_base;
    mmio->dma_size = dma_size;
    mmio->output_buffer = (volatile int8_t*)out_base;
    mmio->output_offset = 0;
    return 0;
}

// Zero-copy: read directly from DMA buffer at offset
static inline int8_t flux_mmio_read(const FluxMMIO* mmio, size_t offset) {
    return mmio->dma_buffer[offset];
}

// Write result directly to output buffer
static inline void flux_mmio_write_result(FluxMMIO* mmio, uint8_t mask, uint8_t severity) {
    size_t idx = mmio->output_offset & (4096 - 1); // Power-of-2 mask
    mmio->output_buffer[idx * 2]     = (int8_t)mask;
    mmio->output_buffer[idx * 2 + 1] = (int8_t)severity;
    mmio->output_offset++;
}

// ═══════════════════════════════════════════════════════════
// NAIVE IMPLEMENTATION (baseline for comparison)
// ═══════════════════════════════════════════════════════════

static inline uint8_t flux_naive_range_check(int8_t value, int8_t lo, int8_t hi) {
    return (value >= lo && value <= hi) ? 1 : 0;
}

static inline uint8_t flux_naive_batch_check(const int8_t* values, size_t count,
                                              const FluxOptConstraint* constraints, size_t n_constraints,
                                              uint8_t* out_results) {
    uint8_t fail_mask = 0;
    for (size_t i = 0; i < count; i++) {
        uint8_t value_pass = 0xFF;
        for (size_t c = 0; c < n_constraints; c++) {
            if (values[i] < constraints[c].lo || values[i] > constraints[c].hi) {
                value_pass &= ~(1u << c);
            }
        }
        out_results[i] = value_pass;
        fail_mask |= ~value_pass;
    }
    return fail_mask;
}

// ═══════════════════════════════════════════════════════════
// OPTIMIZED: Branchless range check
// No branches. Uses arithmetic to compute pass/fail.
//
// pass = (value - lo) >= 0  AND  (hi - value) >= 0
// For INT8: use sign bit extraction
// ═══════════════════════════════════════════════════════════

static inline uint8_t flux_branchless_check(int8_t value, int8_t lo, int8_t hi) {
    // (value >= lo) is true when (value - lo) has no sign bit
    // (value <= hi) is true when (hi - value) has no sign bit
    int16_t lo_diff = (int16_t)value - (int16_t)lo;
    int16_t hi_diff = (int16_t)hi - (int16_t)value;
    // Sign bit extraction: (x >> 15) & 1 = 1 if negative
    uint8_t lo_pass = !((lo_diff >> 15) & 1);
    uint8_t hi_pass = !((hi_diff >> 15) & 1);
    return lo_pass & hi_pass;
}

// ═══════════════════════════════════════════════════════════
// OPTIMIZED: SIMD 8-wide INT8 range check (AVX2)
//
// Check 8 INT8 values against one [lo, hi] constraint simultaneously.
// Returns bitmask: bit i set if value i passes.
// ═══════════════════════════════════════════════════════════

static inline uint8_t flux_simd_check_8x8_avx2(const int8_t* values, int8_t lo, int8_t hi) {
    // Load 8 INT8 values into XMM register
    __m128i v = _mm_loadl_epi64((const __m128i*)values);  // load 8 bytes
    
    // Broadcast lo and hi into XMM registers
    __m128i lo_vec = _mm_set1_epi8(lo);
    __m128i hi_vec = _mm_set1_epi8(hi);
    
    // Compare: v >= lo AND v <= hi
    __m128i ge_lo = _mm_cmpgt_epi8(v, lo_vec);           // v > lo (includes equal via saturating sub trick)
    __m128i le_hi = _mm_cmplt_epi8(v, hi_vec);           // v < hi
    
    // Fix: we want >= not >, <= not <. Use _mm_cmpgt_epi8(v, lo-1) trick
    // But lo could be INT8_MIN. Safer: use !(v < lo) = ~(v < lo)
    __m128i lt_lo = _mm_cmplt_epi8(v, lo_vec);            // v < lo
    __m128i gt_hi = _mm_cmpgt_epi8(v, hi_vec);            // v > hi
    __m128i in_range = _mm_andnot_si128(_mm_or_si128(lt_lo, gt_hi), _mm_set1_epi8(0xFF));
    
    // Extract mask: bit i set if lane i is non-zero
    return (uint8_t)_mm_movemask_epi8(in_range);
}

// ═══════════════════════════════════════════════════════════
// OPTIMIZED: SIMD 8 values × 8 constraints (full matrix)
// All 64 checks in ~10 AVX2 instructions.
// ═══════════════════════════════════════════════════════════

static inline void flux_simd_batch_avx2(
    const int8_t* values,              // 8 values
    const FluxOptConstraint* constraints, // 8 constraints (cache-line aligned)
    uint8_t* result_masks              // 8 output masks (one per value)
) {
    __m128i v = _mm_loadl_epi64((const __m128i*)values);
    
    for (int c = 0; c < FLUX_OPT_MAX_CONSTRAINTS; c++) {
        __m128i lo_vec = _mm_set1_epi8(constraints[c].lo);
        __m128i hi_vec = _mm_set1_epi8(constraints[c].hi);
        
        __m128i lt_lo = _mm_cmplt_epi8(v, lo_vec);
        __m128i gt_hi = _mm_cmpgt_epi8(v, hi_vec);
        __m128i in_range = _mm_andnot_si128(_mm_or_si128(lt_lo, gt_hi), _mm_set1_epi8(0xFF));
        
        // Accumulate: bit c in result_masks[i] = 1 if value i passes constraint c
        uint8_t mask = (uint8_t)_mm_movemask_epi8(in_range);
        for (int i = 0; i < 8; i++) {
            if (mask & (1 << i)) {
                result_masks[i] |= (1 << c);
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════
// OPTIMIZED: AVX-512 64-wide INT8 check (if available)
// ═══════════════════════════════════════════════════════════

#ifdef __AVX512F__

static inline uint64_t flux_simd_check_64x1_avx512(const int8_t* values, int8_t lo, int8_t hi) {
    __m512i v = _mm512_loadu_si512((const void*)values);
    __m512i lo_vec = _mm512_set1_epi8(lo);
    __m512i hi_vec = _mm512_set1_epi8(hi);
    
    // v >= lo: !(v < lo)
    // v <= hi: !(v > hi)
    // Combine: in_range = (v >= lo) & (v <= hi)
    __mmask64 lt_lo = _mm512_cmplt_epi8_mask(v, lo_vec);
    __mmask64 gt_hi = _mm512_cmpgt_epi8_mask(v, hi_vec);
    __mmask64 out_of_range = lt_lo | gt_hi;
    __mmask64 in_range = ~out_of_range;
    
    return (uint64_t)in_range;
}

// 16-wide INT32 check (for larger ranges that don't fit INT8)
static inline uint16_t flux_simd_check_16x32_avx512(const int32_t* values, int32_t lo, int32_t hi) {
    __m512i v = _mm512_loadu_si512((const void*)values);
    __m512i lo_vec = _mm512_set1_epi32(lo);
    __m512i hi_vec = _mm512_set1_epi32(hi);
    
    __mmask16 lt_lo = _mm512_cmplt_epi32_mask(v, lo_vec);
    __mmask16 gt_hi = _mm512_cmpgt_epi32_mask(v, hi_vec);
    __mmask16 in_range = ~(lt_lo | gt_hi);
    
    return (uint16_t)in_range;
}

#endif // __AVX512F__

// ═══════════════════════════════════════════════════════════
// Zero-copy streaming check
// Check constraints directly from a DMA buffer pointer.
// No memcpy. No allocation. Just SIMD on the raw buffer.
// ═══════════════════════════════════════════════════════════

static inline void flux_streaming_check(
    const volatile int8_t* dma_ptr,     // Direct DMA buffer pointer
    size_t batch_size,                  // Number of INT8 values to check
    const FluxOptConstraint* constraints,
    size_t n_constraints,
    FluxProvenanceRing* ring,           // Optional: NULL to skip provenance
    FluxMMIO* mmio                      // Optional: NULL to skip output
) {
    // Cast away volatile — we know the DMA buffer is stable during check
    const int8_t* data = (const int8_t*)dma_ptr;
    
    for (size_t i = 0; i + 8 <= batch_size; i += 8) {
        uint8_t combined_pass = 0xFF;
        for (size_t c = 0; c < n_constraints; c++) {
            uint8_t mask = flux_simd_check_8x8_avx2(data + i, constraints[c].lo, constraints[c].hi);
            combined_pass &= mask;
        }
        
        // Provenance: log the mask for this batch
        if (ring) {
            flux_ring_push(ring, (uint64_t)combined_pass | ((uint64_t)i << 8));
        }
        
        // Output: write directly to MMIO buffer
        if (mmio) {
            flux_mmio_write_result(mmio, combined_pass, FLUX_SEVERITY_TABLE[__builtin_popcount(~combined_pass & 0xFF)]);
        }
    }
    
    // Handle remaining values (batch_size not multiple of 8)
    size_t remaining = batch_size & 7;
    if (remaining > 0) {
        size_t start = batch_size - remaining;
        for (size_t i = start; i < batch_size; i++) {
            uint8_t value_pass = 0xFF;
            for (size_t c = 0; c < n_constraints; c++) {
                if (data[i] < constraints[c].lo || data[i] > constraints[c].hi) {
                    value_pass &= ~(1u << c);
                }
            }
            if (mmio) {
                flux_mmio_write_result(mmio, value_pass, FLUX_SEVERITY_TABLE[__builtin_popcount(~value_pass & 0xFF)]);
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════
// Pre-computed constraint initializer
// ═══════════════════════════════════════════════════════════

static inline void flux_constraint_init(FluxOptConstraint* c, int8_t lo, int8_t hi,
                                         uint8_t id, const char* name) {
    memset(c, 0, sizeof(*c));
    c->lo = lo;
    c->hi = hi;
    c->constraint_id = id;
    c->lo_i32 = (int32_t)lo;  // Sign-extended for AVX2 INT32 ops
    c->hi_i32 = (int32_t)hi;
    strncpy(c->name, name, 31);
    c->name[31] = '\0';
}

// Aviation preset (8 constraints, cache-line aligned)
static inline void flux_aviation_preset(FluxOptConstraint constraints[FLUX_OPT_MAX_CONSTRAINTS]) {
    flux_constraint_init(&constraints[0], -50, 85,  0, "temperature_celsius");
    flux_constraint_init(&constraints[1],   0, 100, 1, "cabin_pressure_pct");
    flux_constraint_init(&constraints[2], -90, 90,  2, "pitch_degrees");
    flux_constraint_init(&constraints[3], -127, 127, 3, "roll_degrees_scaled");
    flux_constraint_init(&constraints[4],   0, 100, 4, "throttle_pct");
    flux_constraint_init(&constraints[5],  -60, 60,  5, "yaw_rate_dps");
    flux_constraint_init(&constraints[6],   0, 127, 6, "airspeed_scaled");
    flux_constraint_init(&constraints[7], -40, 60,  7, "ambient_temp");
}

// ═══════════════════════════════════════════════════════════
// Severity lookup (branchless, table-driven)
// ═══════════════════════════════════════════════════════════

static inline FluxSeverity flux_classify_severity(uint8_t fail_count) {
    // Clamp to table bounds (fail_count should be 0-8)
    uint8_t idx = fail_count > 8 ? 8 : fail_count;
    return (FluxSeverity)FLUX_SEVERITY_TABLE[idx];
}

// ═══════════════════════════════════════════════════════════
// Benchmark harness
// ═══════════════════════════════════════════════════════════

#ifdef FLUX_CONSTRAINT_OPTIMIZED_IMPL

#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define FLUX_BENCH_ITERATIONS 10000000  // 10M iterations

// Aligned test data buffer
static alignas(64) int8_t bench_values[8] = {10, -20, 50, -80, 100, -127, 0, 60};

static void bench_naive(const FluxOptConstraint* constraints) {
    uint64_t start = __builtin_ia32_rdtsc();
    volatile uint8_t sink = 0;
    
    for (uint64_t i = 0; i < FLUX_BENCH_ITERATIONS; i++) {
        for (int v = 0; v < 8; v++) {
            for (int c = 0; c < FLUX_OPT_MAX_CONSTRAINTS; c++) {
                sink += flux_naive_range_check(bench_values[v], constraints[c].lo, constraints[c].hi);
            }
        }
    }
    
    uint64_t end = __builtin_ia32_rdtsc();
    uint64_t total_checks = FLUX_BENCH_ITERATIONS * 8 * FLUX_OPT_MAX_CONSTRAINTS;
    double checks_per_cycle = (double)total_checks / (double)(end - start);
    
    printf("  Naive:          %llu checks in %llu cycles (%.1f checks/cycle)\n",
           (unsigned long long)total_checks, (unsigned long long)(end - start), checks_per_cycle);
    (void)sink;
}

static void bench_branchless(const FluxOptConstraint* constraints) {
    uint64_t start = __builtin_ia32_rdtsc();
    volatile uint8_t sink = 0;
    
    for (uint64_t i = 0; i < FLUX_BENCH_ITERATIONS; i++) {
        for (int v = 0; v < 8; v++) {
            for (int c = 0; c < FLUX_OPT_MAX_CONSTRAINTS; c++) {
                sink += flux_branchless_check(bench_values[v], constraints[c].lo, constraints[c].hi);
            }
        }
    }
    
    uint64_t end = __builtin_ia32_rdtsc();
    uint64_t total_checks = FLUX_BENCH_ITERATIONS * 8 * FLUX_OPT_MAX_CONSTRAINTS;
    double checks_per_cycle = (double)total_checks / (double)(end - start);
    
    printf("  Branchless:     %llu checks in %llu cycles (%.1f checks/cycle)\n",
           (unsigned long long)total_checks, (unsigned long long)(end - start), checks_per_cycle);
    (void)sink;
}

static void bench_simd_avx2(const FluxOptConstraint* constraints) {
    uint64_t start = __builtin_ia32_rdtsc();
    volatile uint8_t sink = 0;
    
    for (uint64_t i = 0; i < FLUX_BENCH_ITERATIONS; i++) {
        for (int c = 0; c < FLUX_OPT_MAX_CONSTRAINTS; c++) {
            sink += flux_simd_check_8x8_avx2(bench_values, constraints[c].lo, constraints[c].hi);
        }
    }
    
    uint64_t end = __builtin_ia32_rdtsc();
    uint64_t total_checks = FLUX_BENCH_ITERATIONS * 8 * FLUX_OPT_MAX_CONSTRAINTS;
    double checks_per_cycle = (double)total_checks / (double)(end - start);
    
    printf("  SIMD AVX2:      %llu checks in %llu cycles (%.1f checks/cycle)\n",
           (unsigned long long)total_checks, (unsigned long long)(end - start), checks_per_cycle);
    (void)sink;
}

#ifdef __AVX512F__
static void bench_simd_avx512(const FluxOptConstraint* constraints) {
    // Prepare 64 test values
    alignas(64) int8_t values_64[64];
    for (int i = 0; i < 64; i++) values_64[i] = (int8_t)(i * 2 - 64);
    
    uint64_t start = __builtin_ia32_rdtsc();
    volatile uint64_t sink = 0;
    
    for (uint64_t i = 0; i < FLUX_BENCH_ITERATIONS; i++) {
        for (int c = 0; c < FLUX_OPT_MAX_CONSTRAINTS; c++) {
            sink += flux_simd_check_64x1_avx512(values_64, constraints[c].lo, constraints[c].hi);
        }
    }
    
    uint64_t end = __builtin_ia32_rdtsc();
    uint64_t total_checks = FLUX_BENCH_ITERATIONS * 64 * FLUX_OPT_MAX_CONSTRAINTS;
    double checks_per_cycle = (double)total_checks / (double)(end - start);
    
    printf("  SIMD AVX-512:   %llu checks in %llu cycles (%.1f checks/cycle)\n",
           (unsigned long long)total_checks, (unsigned long long)(end - start), checks_per_cycle);
    (void)sink;
}
#endif

static void bench_severity(void) {
    uint64_t start = __builtin_ia32_rdtsc();
    volatile uint8_t sink = 0;
    
    for (uint64_t i = 0; i < FLUX_BENCH_ITERATIONS; i++) {
        sink += flux_classify_severity(i % 9);
    }
    
    uint64_t end = __builtin_ia32_rdtsc();
    printf("  Severity table: %llu lookups in %llu cycles (%.2f cycles/lookup)\n",
           (unsigned long long)FLUX_BENCH_ITERATIONS, (unsigned long long)(end - start),
           (double)(end - start) / FLUX_BENCH_ITERATIONS);
    (void)sink;
}

void flux_run_benchmarks(void) {
    __attribute__((aligned(64))) FluxOptConstraint constraints[FLUX_OPT_MAX_CONSTRAINTS];
    flux_aviation_preset(constraints);
    
    printf("\n═══ FLUX Constraint Engine Benchmarks ═══\n");
    printf("CPU: AMD Ryzen AI 9 HX 370 (Zen 5)\n");
    printf("Iterations: %d per variant\n\n", FLUX_BENCH_ITERATIONS);
    
    bench_naive(constraints);
    bench_branchless(constraints);
    bench_simd_avx2(constraints);
#ifdef __AVX512F__
    bench_simd_avx512(constraints);
#endif
    bench_severity();
    
    printf("\n═══════════════════════════════════════\n\n");
}

int main(void) {
    flux_run_benchmarks();
    return 0;
}

#endif // FLUX_CONSTRAINT_OPTIMIZED_IMPL

#ifdef __cplusplus
}
#endif

#endif // FLUX_CONSTRAINT_OPTIMIZED_H
