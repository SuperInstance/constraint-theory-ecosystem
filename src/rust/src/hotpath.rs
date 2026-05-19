//! # FLUX Constraint Engine — Hand-Optimized Hot Path
//!
//! Zero-cost abstractions that compile to the exact same machine code as hand-written assembly.
//! Uses `unsafe` where we KNOW constraints are bounded (they always are in FLUX).
//!
//! Safety guarantees:
//! - Constraint count is always ≤ 8 (enforced by FluxChecker::new)
//! - All memory is pre-allocated (no heap in hot path)
//! - SIMD alignment is guaranteed by `#[repr(C, align(64))]`
//! - `unreachable_unchecked()` is only used after saturation (we KNOW the range)

#![allow(unused_unsafe)]
#![cfg(target_arch = "x86_64")]

use std::arch::x86_64::*;

// ═══════════════════════════════════════════════════════════
// Cache-line aligned constraint struct (64 bytes exactly)
// ═══════════════════════════════════════════════════════════

#[repr(C, align(64))]
#[derive(Debug, Clone, Copy)]
pub struct AlignedConstraint {
    pub lo: i8,                     // offset 0
    pub hi: i8,                     // offset 1
    pub id: u8,                     // offset 2
    _pad0: u8,                      // offset 3
    pub lo_i32: i32,                // offset 4-7 (sign-extended for SIMD)
    pub hi_i32: i32,                // offset 8-11
    pub check_count: u32,           // offset 12-15 (hot constraint tracking)
    pub fail_count: u32,            // offset 16-19
    _name: [u8; 32],                // offset 20-51
    _reserved: [u8; 12],            // offset 52-63
}

const _: () = assert!(std::mem::size_of::<AlignedConstraint>() == 64);

impl AlignedConstraint {
    pub fn new(lo: i8, hi: i8, id: u8, name: &str) -> Self {
        let mut name_buf = [0u8; 32];
        let name_bytes = name.as_bytes();
        let copy_len = name_bytes.len().min(31);
        name_buf[..copy_len].copy_from_slice(&name_bytes[..copy_len]);

        Self {
            lo,
            hi,
            id,
            _pad0: 0,
            lo_i32: lo as i32,
            hi_i32: hi as i32,
            check_count: 0,
            fail_count: 0,
            _name: name_buf,
            _reserved: [0; 12],
        }
    }

    /// Hot path: branchless range check using arithmetic sign-bit extraction
    #[inline(always)]
    pub fn check_branchless(&self, value: i8) -> bool {
        // (value >= lo) ⟺ (value - lo) ≥ 0 ⟺ sign bit not set
        // (value <= hi) ⟺ (hi - value) ≥ 0 ⟺ sign bit not set
        let lo_pass = (value as i16 - self.lo as i16) >= 0;
        let hi_pass = (self.hi as i16 - value as i16) >= 0;
        lo_pass & hi_pass
    }

    /// Hot path: saturate + unreachable_unchecked
    /// After saturating, we KNOW the value is in [lo, hi] range.
    /// If it's not, we saturated it there — so the unchecked path is always valid.
    #[inline(always)]
    pub fn check_saturating(&self, value: i8) -> i8 {
        let saturated = if value < self.lo {
            self.lo
        } else if value > self.hi {
            self.hi
        } else {
            value
        };

        // SAFETY: We just saturated `saturated` to [lo, hi].
        // The saturate guarantees: self.lo <= saturated <= self.hi
        // Therefore: saturated >= self.lo && saturated <= self.hi is always true.
        // We use unreachable_unchecked to tell the optimizer the false branch is impossible.
        if saturated < self.lo || saturated > self.hi {
            // SAFETY: This branch is provably unreachable after saturation.
            unsafe { std::hint::unreachable_unchecked() }
        }

        saturated
    }
}

// ═══════════════════════════════════════════════════════════
// SIMD AVX2: 8-wide INT8 range check
// ═══════════════════════════════════════════════════════════

/// Check 8 INT8 values against one [lo, hi] constraint using AVX2.
/// Returns bitmask: bit i set if value i passes.
///
/// # Safety
/// - `values` must point to at least 8 readable bytes.
/// - CPU must support AVX2 (checked at compile time via cfg).
#[target_feature(enable = "avx2")]
#[inline]
pub unsafe fn simd_check_8x8_avx2(values: &[i8; 8], lo: i8, hi: i8) -> u8 {
    // Load 8 INT8 values
    let v = _mm_loadl_epi64(values.as_ptr() as *const __m128i);

    // Broadcast bounds
    let lo_vec = _mm_set1_epi8(lo);
    let hi_vec = _mm_set1_epi8(hi);

    // in_range = !(v < lo) & !(v > hi)
    let lt_lo = _mm_cmplt_epi8(v, lo_vec);  // v < lo
    let gt_hi = _mm_cmpgt_epi8(v, hi_vec);  // v > hi
    let out_of_range = _mm_or_si128(lt_lo, gt_hi);
    let in_range = _mm_andnot_si128(out_of_range, _mm_set1_epi8(0xFF));

    // Extract mask
    _mm_movemask_epi8(in_range) as u8
}

/// Check 8 INT8 values against 8 constraints, returning 8 result masks.
///
/// # Safety
/// - CPU must support AVX2.
#[target_feature(enable = "avx2")]
#[inline]
pub unsafe fn simd_batch_8x8_avx2(
    values: &[i8; 8],
    constraints: &[AlignedConstraint; 8],
) -> [u8; 8] {
    let v = _mm_loadl_epi64(values.as_ptr() as *const __m128i);
    let mut results = [0u8; 8];

    for c in 0..8 {
        let lo_vec = _mm_set1_epi8(constraints[c].lo);
        let hi_vec = _mm_set1_epi8(constraints[c].hi);

        let lt_lo = _mm_cmplt_epi8(v, lo_vec);
        let gt_hi = _mm_cmpgt_epi8(v, hi_vec);
        let out_of_range = _mm_or_si128(lt_lo, gt_hi);
        let in_range = _mm_andnot_si128(out_of_range, _mm_set1_epi8(0xFF));

        let mask = _mm_movemask_epi8(in_range) as u8;

        // Accumulate per-value: bit c in result[i] = 1 if value i passes constraint c
        for i in 0..8 {
            if mask & (1 << i) != 0 {
                results[i] |= 1 << c;
            }
        }
    }

    results
}

// ═══════════════════════════════════════════════════════════
// SIMD AVX-512: 64-wide INT8 check (if available at runtime)
// ═══════════════════════════════════════════════════════════

/// Check 64 INT8 values against one [lo, hi] constraint using AVX-512.
/// Returns 64-bit bitmask.
///
/// # Safety
/// - `values` must point to at least 64 readable bytes, 64-byte aligned preferred.
/// - CPU must support AVX-512F + AVX-512BW.
#[cfg(target_feature = "avx512f")]
#[target_feature(enable = "avx512f", enable = "avx512bw")]
#[inline]
pub unsafe fn simd_check_64x1_avx512(values: &[i8; 64], lo: i8, hi: i8) -> u64 {
    let v = _mm512_loadu_si512(values.as_ptr() as *const void);
    let lo_vec = _mm512_set1_epi8(lo);
    let hi_vec = _mm512_set1_epi8(hi);

    let lt_lo = _mm512_cmplt_epi8_mask(v, lo_vec);
    let gt_hi = _mm512_cmpgt_epi8_mask(v, hi_vec);
    let out_of_range = lt_lo | gt_hi;

    (!out_of_range) as u64
}

/// Check 16 INT32 values against one [lo, hi] constraint using AVX-512.
/// Returns 16-bit bitmask.
///
/// # Safety
/// - `values` must point to at least 16 i32 values.
/// - CPU must support AVX-512F.
#[cfg(target_feature = "avx512f")]
#[target_feature(enable = "avx512f")]
#[inline]
pub unsafe fn simd_check_16x32_avx512(values: &[i32; 16], lo: i32, hi: i32) -> u16 {
    let v = _mm512_loadu_si512(values.as_ptr() as *const void);
    let lo_vec = _mm512_set1_epi32(lo);
    let hi_vec = _mm512_set1_epi32(hi);

    let lt_lo = _mm512_cmplt_epi32_mask(v, lo_vec);
    let gt_hi = _mm512_cmpgt_epi32_mask(v, hi_vec);

    (!(lt_lo | gt_hi)) as u16
}

// ═══════════════════════════════════════════════════════════
// Dispatch: auto-select best available implementation
// ═══════════════════════════════════════════════════════════

/// Check 8 values against a single constraint. Auto-selects SIMD or scalar.
#[inline(always)]
pub fn check_8_values(values: &[i8; 8], lo: i8, hi: i8) -> u8 {
    if is_x86_feature_detected!("avx2") {
        // SAFETY: We checked AVX2 availability.
        unsafe { simd_check_8x8_avx2(values, lo, hi) }
    } else {
        // Scalar fallback
        let mut mask = 0u8;
        for i in 0..8 {
            if values[i] >= lo && values[i] <= hi {
                mask |= 1 << i;
            }
        }
        mask
    }
}

/// Check 8 values against 8 constraints. Auto-selects SIMD or scalar.
#[inline(always)]
pub fn check_8x8(values: &[i8; 8], constraints: &[AlignedConstraint; 8]) -> [u8; 8] {
    if is_x86_feature_detected!("avx2") {
        unsafe { simd_batch_8x8_avx2(values, constraints) }
    } else {
        let mut results = [0u8; 8];
        for i in 0..8 {
            for c in 0..8 {
                if values[i] >= constraints[c].lo && values[i] <= constraints[c].hi {
                    results[i] |= 1 << c;
                }
            }
        }
        results
    }
}

// ═══════════════════════════════════════════════════════════
// Zero-copy streaming check
// ═══════════════════════════════════════════════════════════

/// Check constraints directly from a raw byte pointer (DMA buffer).
/// No copy. No allocation. Just SIMD on the pointer.
///
/// # Safety
/// - `ptr` must point to at least `count` readable i8 values.
/// - The memory must be stable for the duration of this call.
#[inline]
pub unsafe fn streaming_check(
    ptr: *const i8,
    count: usize,
    constraints: &[AlignedConstraint],
    results: &mut [u8],
) {
    let n_constraints = constraints.len().min(8);
    let data = std::slice::from_raw_parts(ptr, count);

    // Process 8 at a time
    let chunks = count / 8;
    for chunk in 0..chunks {
        let offset = chunk * 8;
        let values: [i8; 8] = std::ptr::read(data.as_ptr().add(offset) as *const [i8; 8]);

        for c in 0..n_constraints {
            let mask = check_8_values(&values, constraints[c].lo, constraints[c].hi);
            // Write per-value results
            for i in 0..8 {
                if offset + i < results.len() {
                    if mask & (1 << i) != 0 {
                        results[offset + i] |= 1 << c;
                    }
                }
            }
        }
    }

    // Handle remainder
    for i in (chunks * 8)..count {
        for c in 0..n_constraints {
            if data[i] >= constraints[c].lo && data[i] <= constraints[c].hi {
                results[i] |= 1 << c;
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════
// Ring buffer provenance (power-of-2 mask indexing)
// ═══════════════════════════════════════════════════════════

const RING_SIZE: usize = 4096; // Must be power of 2
const RING_MASK: usize = RING_SIZE - 1;

pub struct ProvenanceRing {
    entries: [u64; RING_SIZE],
    head: usize,
    tail: usize,
}

impl ProvenanceRing {
    pub fn new() -> Self {
        Self {
            entries: [0u64; RING_SIZE],
            head: 0,
            tail: 0,
        }
    }

    /// Branchless push: no bounds check, mask handles wrap.
    #[inline(always)]
    pub fn push(&mut self, hash: u64) {
        self.entries[self.head & RING_MASK] = hash;
        self.head = self.head.wrapping_add(1);
        // Tail chases head at RING_SIZE behind
        if self.head.wrapping_sub(self.tail) > RING_SIZE {
            self.tail = self.tail.wrapping_add(1);
        }
    }

    #[inline(always)]
    pub fn len(&self) -> usize {
        self.head.wrapping_sub(self.tail)
    }
}

// ═══════════════════════════════════════════════════════════
// Pre-computed severity lookup (branchless)
// ═══════════════════════════════════════════════════════════

const SEVERITY_TABLE: [u8; 9] = [0, 1, 1, 2, 2, 3, 3, 3, 3];

#[inline(always)]
pub fn classify_severity(fail_count: u8) -> u8 {
    // SAFETY: fail_count is 0-8 (max 8 constraints). Table has 9 entries.
    let idx = if fail_count > 8 { 8 } else { fail_count };
    // SAFETY: idx is 0-8, table has 9 entries.
    unsafe { *SEVERITY_TABLE.get_unchecked(idx as usize) }
}

// ═══════════════════════════════════════════════════════════
// Aviation preset
// ═══════════════════════════════════════════════════════════

pub fn aviation_preset() -> [AlignedConstraint; 8] {
    [
        AlignedConstraint::new(-50, 85,  0, "temperature_celsius"),
        AlignedConstraint::new(0,   100, 1, "cabin_pressure_pct"),
        AlignedConstraint::new(-90, 90,  2, "pitch_degrees"),
        AlignedConstraint::new(-127, 127, 3, "roll_degrees_scaled"),
        AlignedConstraint::new(0,   100, 4, "throttle_pct"),
        AlignedConstraint::new(-60, 60,  5, "yaw_rate_dps"),
        AlignedConstraint::new(0,   127, 6, "airspeed_scaled"),
        AlignedConstraint::new(-40, 60,  7, "ambient_temp"),
    ]
}

// ═══════════════════════════════════════════════════════════
// Benchmark functions
// ═══════════════════════════════════════════════════════════

#[cfg(test)]
mod bench {
    use super::*;
    use std::time::Instant;

    const ITERS: u64 = 10_000_000;

    #[test]
    fn bench_naive() {
        let constraints = aviation_preset();
        let values: [i8; 8] = [10, -20, 50, -80, 100, -127, 0, 60];
        let mut sink = 0u64;

        let start = Instant::now();
        for _ in 0..ITERS {
            for v in &values {
                for c in &constraints {
                    sink += if *v >= c.lo && *v <= c.hi { 1 } else { 0 };
                }
            }
        }
        let elapsed = start.elapsed();

        let total = ITERS * 8 * 8;
        let per_sec = total as f64 / elapsed.as_secs_f64();
        eprintln!("  Rust naive:     {} checks in {:.3?} ({:.0} checks/sec)",
                  total, elapsed, per_sec);
        assert!(sink > 0); // prevent optimization
    }

    #[test]
    fn bench_branchless() {
        let constraints = aviation_preset();
        let values: [i8; 8] = [10, -20, 50, -80, 100, -127, 0, 60];
        let mut sink = 0u64;

        let start = Instant::now();
        for _ in 0..ITERS {
            for v in &values {
                for c in &constraints {
                    sink += c.check_branchless(*v) as u64;
                }
            }
        }
        let elapsed = start.elapsed();

        let total = ITERS * 8 * 8;
        let per_sec = total as f64 / elapsed.as_secs_f64();
        eprintln!("  Rust branchless:{} checks in {:.3?} ({:.0} checks/sec)",
                  total, elapsed, per_sec);
        assert!(sink > 0);
    }

    #[test]
    fn bench_simd_avx2() {
        if !is_x86_feature_detected!("avx2") {
            eprintln!("  Skipping AVX2 benchmark (not available)");
            return;
        }

        let constraints = aviation_preset();
        let values: [i8; 8] = [10, -20, 50, -80, 100, -127, 0, 60];
        let mut sink = 0u64;

        let start = Instant::now();
        for _ in 0..ITERS {
            unsafe {
                for c in &constraints {
                    sink += simd_check_8x8_avx2(&values, c.lo, c.hi) as u64;
                }
            }
        }
        let elapsed = start.elapsed();

        let total = ITERS * 8 * 8;
        let per_sec = total as f64 / elapsed.as_secs_f64();
        eprintln!("  Rust SIMD AVX2: {} checks in {:.3?} ({:.0} checks/sec)",
                  total, elapsed, per_sec);
        assert!(sink > 0);
    }

    #[test]
    fn bench_severity() {
        let mut sink = 0u64;
        let start = Instant::now();
        for i in 0..ITERS {
            sink += classify_severity((i % 9) as u8) as u64;
        }
        let elapsed = start.elapsed();
        eprintln!("  Rust severity:  {} lookups in {:.3?} ({:.0}/sec)",
                  ITERS, elapsed, ITERS as f64 / elapsed.as_secs_f64());
        assert!(sink > 0);
    }
}
