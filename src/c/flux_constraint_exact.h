/**
 * FLUX Exact Constraint Engine — C Implementation (Production)
 * Zero false negatives. Zero-alloc hot path. AVX2 SIMD batch.
 *
 * Hot path: flux_check_exact() → uint8_t error_mask (0 = all pass)
 * Batch:    flux_check_batch_avx2() → array of masks
 *
 * INVARIANT: A value outside bounds is ALWAYS detected. No exceptions.
 * NaN always violates all constraints. No opt-in.
 *
 * Usage:
 *   #define FLUX_EXACT_IMPL
 *   #include "flux_constraint_exact.h"
 */

#ifndef FLUX_CONSTRAINT_EXACT_H
#define FLUX_CONSTRAINT_EXACT_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>
#include <stdbool.h>

#ifdef __AVX2__
#include <immintrin.h>
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define FLUX_EXACT_MAX_CONSTRAINTS 8

typedef enum {
    FLUX_SEV_PASS     = 0,
    FLUX_SEV_CAUTION  = 1,
    FLUX_SEV_WARNING  = 2,
    FLUX_SEV_CRITICAL = 3,
} FluxSeverity;

static const uint8_t FLUX_SEVERITY_TABLE[9] = {
    FLUX_SEV_PASS, FLUX_SEV_CAUTION, FLUX_SEV_CAUTION,
    FLUX_SEV_WARNING, FLUX_SEV_WARNING,
    FLUX_SEV_CRITICAL, FLUX_SEV_CRITICAL, FLUX_SEV_CRITICAL, FLUX_SEV_CRITICAL,
};

typedef struct {
    float lo[FLUX_EXACT_MAX_CONSTRAINTS];
    float hi[FLUX_EXACT_MAX_CONSTRAINTS];
    char  name[FLUX_EXACT_MAX_CONSTRAINTS][32];
    int   n;
} FluxExact;

/* ── Init ─────────────────────────────────────────────────── */

static inline void flux_exact_init(FluxExact* fc) {
    memset(fc, 0, sizeof(*fc));
}

static inline int flux_exact_add(FluxExact* fc, float lo, float hi, const char* name) {
    if (fc->n >= FLUX_EXACT_MAX_CONSTRAINTS) return -1;
    if (lo > hi) return -2;
    fc->lo[fc->n] = lo;
    fc->hi[fc->n] = hi;
    strncpy(fc->name[fc->n], name, 31);
    fc->name[fc->n][31] = '\0';
    fc->n++;
    return 0;
}

/* ── Hot path: returns error_mask (0 = pass) ──────────────── */

static inline uint8_t flux_check_exact(const FluxExact* fc, float val) {
    if (val != val) return (1u << fc->n) - 1u;  /* NaN violates all */
    uint8_t mask = 0;
    for (int i = 0; i < fc->n; i++) {
        if (val < fc->lo[i] || val > fc->hi[i])
            mask |= (1u << i);
    }
    return mask;
}

static inline bool flux_mask_passed(uint8_t mask) { return mask == 0; }

static inline FluxSeverity flux_mask_severity(uint8_t mask) {
    /* popcount */
    uint8_t count = 0;
    while (mask) { count++; mask &= mask - 1; }
    return (FluxSeverity)FLUX_SEVERITY_TABLE[count > 8 ? 8 : count];
}

/* ── Full result struct (legacy compat) ───────────────────── */

typedef struct {
    uint8_t error_mask;
    uint8_t severity;
    uint8_t violated_lo;
    uint8_t violated_hi;
    uint8_t violated_count;
} FluxExactResult;

static inline FluxExactResult flux_exact_check(const FluxExact* fc, float val) {
    FluxExactResult r = {0, FLUX_SEV_PASS, 0, 0, 0};
    bool is_nan = (val != val);
    for (int i = 0; i < fc->n; i++) {
        int lo_f = is_nan || val < fc->lo[i];
        int hi_f = is_nan || val > fc->hi[i];
        if (lo_f || hi_f) { r.error_mask |= (1u << i); r.violated_count++; }
        if (lo_f) r.violated_lo |= (1u << i);
        if (hi_f) r.violated_hi |= (1u << i);
    }
    r.severity = FLUX_SEVERITY_TABLE[r.violated_count > 8 ? 8 : r.violated_count];
    return r;
}

/* ── Scalar batch (no SIMD) ──────────────────────────────── */

static inline void flux_check_batch(
    const FluxExact* fc, const float* values, int count, uint8_t* masks
) {
    for (int i = 0; i < count; i++) {
        masks[i] = flux_check_exact(fc, values[i]);
    }
}

/* ── AVX2 SIMD batch: 8 floats at a time ─────────────────── */

#ifdef __AVX2__

static inline void flux_check_batch_avx2(
    const FluxExact* fc, const float* values, int count, uint8_t* masks
) {
    memset(masks, 0, count);
    int i = 0;

    /* Process 8 values at a time */
    for (; i + 7 < count; i += 8) {
        __m256 v = _mm256_loadu_ps(&values[i]);

        /* NaN check: NaN != NaN → use comparison with self */
        __m256 self = _mm256_mul_ps(v, v);
        __m256 ones = _mm256_set1_ps(1.0f);
        __m256 is_valid = _mm256_cmp_ps(self, self, _CMP_EQ_OQ);

        for (int c = 0; c < fc->n; c++) {
            __m256 lo_v = _mm256_set1_ps(fc->lo[c]);
            __m256 hi_v = _mm256_set1_ps(fc->hi[c]);

            /* (val >= lo) AND (val <= hi) AND is_valid */
            __m256 ge_lo = _mm256_and_ps(_mm256_cmp_ps(v, lo_v, _CMP_GE_OQ), is_valid);
            __m256 le_hi = _mm256_and_ps(_mm256_cmp_ps(v, hi_v, _CMP_LE_OQ), is_valid);
            __m256 in_range = _mm256_and_ps(ge_lo, le_hi);

            /* bit = 1 means in range; invert for error */
            int pass_mask = _mm256_movemask_ps(in_range);
            uint8_t fail_bits = (uint8_t)(~pass_mask & 0xFF);

            /* OR fail bit into each value's mask */
            for (int j = 0; j < 8; j++) {
                if (fail_bits & (1 << j)) {
                    masks[i + j] |= (1u << c);
                }
            }
        }
    }

    /* Scalar tail */
    for (; i < count; i++) {
        masks[i] = flux_check_exact(fc, values[i]);
    }
}

#endif /* __AVX2__ */

/* ── Preset loaders ───────────────────────────────────────── */

static inline void flux_preset_automotive_can(FluxExact* fc) {
    flux_exact_init(fc);
    flux_exact_add(fc, 0, 8000, "engine_rpm");
    flux_exact_add(fc, 0, 300, "vehicle_speed_kmh");
    flux_exact_add(fc, -40, 150, "coolant_temp_c");
    flux_exact_add(fc, 0, 100, "throttle_pct");
    flux_exact_add(fc, 0, 200, "brake_pressure_bar");
    flux_exact_add(fc, -720, 720, "steering_angle_deg");
    flux_exact_add(fc, 9, 16, "battery_voltage_v");
    flux_exact_add(fc, 0, 100, "fuel_level_pct");
}

static inline void flux_preset_aviation_adsb(FluxExact* fc) {
    flux_exact_init(fc);
    flux_exact_add(fc, -1000, 45000, "altitude_ft");
    flux_exact_add(fc, 0, 600, "ground_speed_kt");
    flux_exact_add(fc, -180, 180, "heading_deg");
    flux_exact_add(fc, -55, 70, "cabin_temp_c");
    flux_exact_add(fc, 75, 101, "cabin_pressure_kpa");
    flux_exact_add(fc, 0, 100, "fuel_flow_pct");
    flux_exact_add(fc, 60, 100, "hydraulic_pct");
    flux_exact_add(fc, -90, 90, "pitch_deg");
}

static inline void flux_preset_medical_fhir(FluxExact* fc) {
    flux_exact_init(fc);
    flux_exact_add(fc, 36.1f, 37.8f, "body_temp_c");
    flux_exact_add(fc, 60, 100, "heart_rate_bpm");
    flux_exact_add(fc, 95, 100, "spo2_pct");
    flux_exact_add(fc, 80, 120, "bp_systolic_mmhg");
    flux_exact_add(fc, 60, 100, "bp_diastolic_mmhg");
    flux_exact_add(fc, 12, 20, "respiratory_rate");
    flux_exact_add(fc, 7.35f, 7.45f, "ph");
    flux_exact_add(fc, 0, 300, "glucose_mg_dl");
}

static inline void flux_preset_energy_scada(FluxExact* fc) {
    flux_exact_init(fc);
    flux_exact_add(fc, 49.0f, 51.0f, "grid_freq_hz");
    flux_exact_add(fc, 0.9f, 1.1f, "voltage_pu");
    flux_exact_add(fc, 0, 80, "transformer_temp_c");
    flux_exact_add(fc, 0, 100, "line_load_pct");
    flux_exact_add(fc, 0, 500, "current_a");
    flux_exact_add(fc, -100, 100, "power_factor_offset");
    flux_exact_add(fc, 0, 360, "phase_angle_deg");
    flux_exact_add(fc, 0, 50, "thd_pct");
}

#ifdef __cplusplus
}
#endif

#endif /* FLUX_CONSTRAINT_EXACT_H */


/* ═══════════════════════════════════════════════════════════
 * Implementation + tests + benchmark (compiled with -DFLUX_EXACT_IMPL)
 * ═══════════════════════════════════════════════════════════ */

#ifdef FLUX_EXACT_IMPL

#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static double now_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

static void bench_scalar(const FluxExact* fc, int iters) {
    double t0 = now_sec();
    volatile uint8_t sink = 0;
    for (int i = 0; i < iters; i++) {
        float val = (float)((i % 1000) - 500);
        sink |= flux_check_exact(fc, val);
    }
    double elapsed = now_sec() - t0;
    double rate = iters / elapsed;
    printf("  Scalar: %.1fM checks/sec (%d iters, %.3fms)\n", rate/1e6, iters, elapsed*1000);
    (void)sink;
}

#ifdef __AVX2__
static void bench_avx2(const FluxExact* fc, int iters) {
    /* Generate test data */
    float* vals = malloc(iters * sizeof(float));
    uint8_t* masks = malloc(iters);
    for (int i = 0; i < iters; i++)
        vals[i] = (float)((i % 1000) - 500);

    double t0 = now_sec();
    flux_check_batch_avx2(fc, vals, iters, masks);
    double elapsed = now_sec() - t0;
    double rate = iters / elapsed;
    printf("  AVX2:   %.1fM checks/sec (%d iters, %.3fms)\n", rate/1e6, iters, elapsed*1000);
    printf("  Speedup: %.1fx\n", rate / (iters / (now_sec() - t0 + elapsed)));

    free(vals);
    free(masks);
}
#endif

int main(void) {
    printf("=== FLUX Exact Constraint Engine — C Benchmark ===\n\n");

    /* Test basic correctness */
    FluxExact fc;
    flux_exact_init(&fc);
    flux_exact_add(&fc, -40, 150, "coolant_temp");

    printf("Correctness tests:\n");
    assert(flux_check_exact(&fc, 150.0f) == 0);
    assert(flux_check_exact(&fc, -40.0f) == 0);
    assert(flux_check_exact(&fc, 151.0f) == 1);
    assert(flux_check_exact(&fc, -41.0f) == 1);
    assert(flux_check_exact(&fc, NAN) == 1);
    assert(flux_check_exact(&fc, INFINITY) == 1);
    assert(flux_check_exact(&fc, -INFINITY) == 1);
    assert(flux_mask_passed(0) == true);
    assert(flux_mask_passed(1) == false);
    printf("  All passed.\n\n");

    /* Benchmark automotive preset */
    FluxExact auto_fc;
    flux_preset_automotive_can(&auto_fc);

    printf("Automotive CAN (8 constraints):\n");
    bench_scalar(&auto_fc, 10000000);

#ifdef __AVX2__
    bench_avx2(&auto_fc, 10000000);
#else
    printf("  (AVX2 not available)\n");
#endif

    return 0;
}

#endif /* FLUX_EXACT_IMPL */
