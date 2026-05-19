/**
 * FLUX Exact Constraint Engine — C Implementation
 * Zero false negatives. Bounds and values in original numeric space.
 * SIMD-accelerated via AVX2 float comparisons.
 *
 * INVARIANT: A value outside bounds is ALWAYS detected. No exceptions.
 *
 * Usage:
 *   #define FLUX_EXACT_IMPL
 *   #include "flux_constraint_exact.h"
 *
 * (c) 2026 SuperInstance — Apache 2.0
 */

#ifndef FLUX_CONSTRAINT_EXACT_H
#define FLUX_CONSTRAINT_EXACT_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>

#ifdef __AVX2__
#include <immintrin.h>
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* ═══════════════════════════════════════════════════════════
 * Configuration
 * ═══════════════════════════════════════════════════════════ */

#define FLUX_EXACT_MAX_CONSTRAINTS  8

/* ═══════════════════════════════════════════════════════════
 * Severity levels
 * ═══════════════════════════════════════════════════════════ */

typedef enum {
    FLUX_EXACT_SEV_PASS     = 0,
    FLUX_EXACT_SEV_CAUTION  = 1,
    FLUX_EXACT_SEV_WARNING  = 2,
    FLUX_EXACT_SEV_CRITICAL = 3,
} FluxExactSeverity;

/* ═══════════════════════════════════════════════════════════
 * Pre-computed severity lookup table (9 bytes)
 * Index: number of failed constraints (0-8)
 * ═══════════════════════════════════════════════════════════ */

static const uint8_t FLUX_EXACT_SEVERITY_TABLE[9] = {
    FLUX_EXACT_SEV_PASS,
    FLUX_EXACT_SEV_CAUTION,
    FLUX_EXACT_SEV_CAUTION,
    FLUX_EXACT_SEV_WARNING,
    FLUX_EXACT_SEV_WARNING,
    FLUX_EXACT_SEV_CRITICAL,
    FLUX_EXACT_SEV_CRITICAL,
    FLUX_EXACT_SEV_CRITICAL,
    FLUX_EXACT_SEV_CRITICAL,
};

/* ═══════════════════════════════════════════════════════════
 * Constraint definition — bounds stored as ORIGINAL float values
 * ═══════════════════════════════════════════════════════════ */

typedef struct {
    float lo;          /* Lower bound — ORIGINAL value, NOT quantized */
    float hi;          /* Upper bound — ORIGINAL value, NOT quantized */
    char   name[32];   /* Human-readable identifier */
} FluxExactConstraint;

/* ═══════════════════════════════════════════════════════════
 * Result structure
 * ═══════════════════════════════════════════════════════════ */

typedef struct {
    uint8_t  error_mask;      /* Bit i set = constraint i violated */
    uint8_t  severity;        /* From FLUX_EXACT_SEVERITY_TABLE */
    uint8_t  violated_lo;     /* Bitmask of lower-bound violations */
    uint8_t  violated_hi;     /* Bitmask of upper-bound violations */
    uint8_t  violated_count;  /* Popcount of error_mask */
    uint8_t  _pad[3];
} FluxExactResult;

/* ═══════════════════════════════════════════════════════════
 * Constraint set (up to 8 constraints)
 * ═══════════════════════════════════════════════════════════ */

typedef struct {
    FluxExactConstraint constraints[FLUX_EXACT_MAX_CONSTRAINTS];
    uint8_t n_constraints;
} FluxExactChecker;

/* ═══════════════════════════════════════════════════════════
 * Initialization
 * ═══════════════════════════════════════════════════════════ */

static inline void flux_exact_init(FluxExactChecker* fc) {
    memset(fc, 0, sizeof(*fc));
}

static inline int flux_exact_add_constraint(
    FluxExactChecker* fc,
    float lo, float hi,
    const char* name
) {
    if (fc->n_constraints >= FLUX_EXACT_MAX_CONSTRAINTS) return -1;
    if (lo > hi) return -2;

    FluxExactConstraint* c = &fc->constraints[fc->n_constraints];
    c->lo = lo;
    c->hi = hi;
    strncpy(c->name, name, 31);
    c->name[31] = '\0';
    fc->n_constraints++;
    return 0;
}

/* ═══════════════════════════════════════════════════════════
 * Core check — EXACT comparison in original numeric space
 *
 * INVARIANT: No quantization of bounds or values.
 *            value is compared EXACTLY against lo and hi.
 *            ZERO false negatives guaranteed.
 * ═══════════════════════════════════════════════════════════ */

static inline FluxExactResult flux_exact_check(
    const FluxExactChecker* fc,
    float value
) {
    FluxExactResult r;
    r.error_mask    = 0;
    r.severity      = FLUX_EXACT_SEV_PASS;
    r.violated_lo   = 0;
    r.violated_hi   = 0;
    r.violated_count = 0;
    memset(r._pad, 0, sizeof(r._pad));

    for (uint8_t i = 0; i < fc->n_constraints; i++) {
        const FluxExactConstraint* c = &fc->constraints[i];
        int lo_fail = (value < c->lo) ? 1 : 0;
        int hi_fail = (value > c->hi) ? 1 : 0;

        if (lo_fail || hi_fail) {
            r.error_mask |= (1u << i);
            r.violated_count++;
        }
        if (lo_fail) r.violated_lo |= (1u << i);
        if (hi_fail) r.violated_hi |= (1u << i);
    }

    /* Severity from lookup table */
    uint8_t idx = r.violated_count > 8 ? 8 : r.violated_count;
    r.severity = FLUX_EXACT_SEVERITY_TABLE[idx];

    return r;
}

/* ═══════════════════════════════════════════════════════════
 * Batch check — process array of values
 * ═══════════════════════════════════════════════════════════ */

static inline void flux_exact_check_batch(
    const FluxExactChecker* fc,
    const float* values,
    size_t count,
    FluxExactResult* results
) {
    for (size_t i = 0; i < count; i++) {
        results[i] = flux_exact_check(fc, values[i]);
    }
}

/* ═══════════════════════════════════════════════════════════
 * SIMD 8-wide float comparison (AVX2)
 * Check 8 float values against one [lo, hi] constraint simultaneously.
 * All comparisons in ORIGINAL float space — no quantization.
 * ═══════════════════════════════════════════════════════════ */

#ifdef __AVX2__

static inline uint8_t flux_exact_simd_check_8f(
    const float* values,     /* 8 floats */
    float lo, float hi
) {
    __m256 v = _mm256_loadu_ps(values);
    __m256 lo_vec = _mm256_set1_ps(lo);
    __m256 hi_vec = _mm256_set1_ps(hi);

    /* value >= lo AND value <= hi */
    __m256 ge_lo = _mm256_cmp_ps(v, lo_vec, _CMP_GE_OQ);
    __m256 le_hi = _mm256_cmp_ps(v, hi_vec, _CMP_LE_OQ);
    __m256 in_range = _mm256_and_ps(ge_lo, le_hi);

    /* movemask: bit i = sign bit of lane i. All-ones = in range. */
    int mask = _mm256_movemask_ps(in_range);
    /* mask bit i = 1 if value i is in range. Invert for error mask. */
    return (uint8_t)(~mask & 0xFF);
}

/* Full 8×8 matrix: 8 values × 8 constraints */
static inline void flux_exact_simd_batch_8x8(
    const float* values,                     /* 8 floats */
    const FluxExactConstraint* constraints,  /* up to 8 constraints */
    uint8_t n_constraints,
    uint8_t* error_masks                     /* 8 output masks */
) {
    memset(error_masks, 0, 8);

    __m256 v = _mm256_loadu_ps(values);

    for (uint8_t c = 0; c < n_constraints; c++) {
        __m256 lo_vec = _mm256_set1_ps(constraints[c].lo);
        __m256 hi_vec = _mm256_set1_ps(constraints[c].hi);

        __m256 ge_lo = _mm256_cmp_ps(v, lo_vec, _CMP_GE_OQ);
        __m256 le_hi = _mm256_cmp_ps(v, hi_vec, _CMP_LE_OQ);
        __m256 in_range = _mm256_and_ps(ge_lo, le_hi);

        int mask = _mm256_movemask_ps(in_range);
        /* bit i in pass_mask = 1 if value i passes constraint c */
        uint8_t fail_bits = (uint8_t)(~mask & 0xFF);

        for (int i = 0; i < 8; i++) {
            if (fail_bits & (1 << i)) {
                error_masks[i] |= (1 << c);
            }
        }
    }
}

#endif /* __AVX2__ */

/* ═══════════════════════════════════════════════════════════
 * Preset loaders
 * ═══════════════════════════════════════════════════════════ */

static inline void flux_exact_preset_automotive_can(FluxExactChecker* fc) {
    flux_exact_init(fc);
    flux_exact_add_constraint(fc, 0, 8000,   "engine_rpm");
    flux_exact_add_constraint(fc, 0, 300,    "vehicle_speed_kmh");
    flux_exact_add_constraint(fc, -40, 150,  "coolant_temp_c");
    flux_exact_add_constraint(fc, 0, 100,    "throttle_pct");
    flux_exact_add_constraint(fc, 0, 200,    "brake_pressure_bar");
    flux_exact_add_constraint(fc, -720, 720, "steering_angle_deg");
    flux_exact_add_constraint(fc, 9, 16,     "battery_voltage_v");
    flux_exact_add_constraint(fc, 0, 100,    "fuel_level_pct");
}

static inline void flux_exact_preset_aviation_adsb(FluxExactChecker* fc) {
    flux_exact_init(fc);
    flux_exact_add_constraint(fc, -1000, 45000, "altitude_ft");
    flux_exact_add_constraint(fc, 0, 600,       "ground_speed_kt");
    flux_exact_add_constraint(fc, -180, 180,    "heading_deg");
    flux_exact_add_constraint(fc, -55, 70,      "cabin_temp_c");
    flux_exact_add_constraint(fc, 75, 101,      "cabin_pressure_kpa");
    flux_exact_add_constraint(fc, 0, 100,       "fuel_flow_pct");
    flux_exact_add_constraint(fc, 60, 100,      "hydraulic_pct");
    flux_exact_add_constraint(fc, -90, 90,      "pitch_deg");
}

static inline void flux_exact_preset_medical_fhir(FluxExactChecker* fc) {
    flux_exact_init(fc);
    flux_exact_add_constraint(fc, 36.1f, 37.8f,  "body_temp_c");
    flux_exact_add_constraint(fc, 60, 100,        "heart_rate_bpm");
    flux_exact_add_constraint(fc, 95, 100,        "spo2_pct");
    flux_exact_add_constraint(fc, 80, 120,        "bp_systolic_mmhg");
    flux_exact_add_constraint(fc, 60, 100,        "bp_diastolic_mmhg");
    flux_exact_add_constraint(fc, 12, 20,         "respiratory_rate");
    flux_exact_add_constraint(fc, 7.35f, 7.45f,   "ph");
    flux_exact_add_constraint(fc, 0, 300,         "glucose_mg_dl");
}

static inline void flux_exact_preset_energy_scada(FluxExactChecker* fc) {
    flux_exact_init(fc);
    flux_exact_add_constraint(fc, 49.0f, 51.0f,  "grid_freq_hz");
    flux_exact_add_constraint(fc, 0.9f, 1.1f,    "voltage_pu");
    flux_exact_add_constraint(fc, 0, 80,          "transformer_temp_c");
    flux_exact_add_constraint(fc, 0, 100,         "line_load_pct");
    flux_exact_add_constraint(fc, 0, 500,         "current_a");
    flux_exact_add_constraint(fc, -100, 100,      "power_factor_offset");
    flux_exact_add_constraint(fc, 0, 360,         "phase_angle_deg");
    flux_exact_add_constraint(fc, 0, 50,          "thd_pct");
}

#ifdef __cplusplus
}
#endif

#endif /* FLUX_CONSTRAINT_EXACT_H */
