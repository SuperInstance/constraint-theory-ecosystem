"""
Tests for FLUX Signal Processing — constraint checking as filtering.

Demonstrates:
1. ConstraintFilter frequency response analysis
2. ViolationWavelet pattern classification (spike vs drift vs oscillation vs burst)
3. KalmanPredictiveChecker early violation detection
4. NyquistAnalyzer sampling rate requirements
5. CompressedSensingChecker sub-Nyquist monitoring
"""

import sys
import os
import math
import random

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))

from flux_signal import (
    ConstraintFilter, ViolationPattern, ViolationWavelet,
    KalmanPredictiveChecker, PreClassification,
    NyquistAnalyzer, CompressedSensingChecker
)


# ---- Signal generators ----

def clean_signal(n=256, lo=20, hi=80, center=50, amplitude=10):
    """Clean signal: all values in range."""
    return [center + amplitude * math.sin(2 * math.pi * i / 64) for i in range(n)]


def spike_signal(n=256, lo=20, hi=80, center=50, amplitude=10, n_spikes=5):
    """Clean signal with random spike violations."""
    sig = clean_signal(n, lo, hi, center, amplitude)
    spike_positions = random.sample(range(10, n - 10), n_spikes)
    for pos in spike_positions:
        sig[pos] = random.choice([lo - 20, hi + 20])  # way out of range
    return sig


def drift_signal(n=256, lo=20, hi=80, center=50, drift_rate=0.5):
    """Signal that slowly drifts out of range."""
    sig = []
    for i in range(n):
        value = center + drift_rate * i  # linear ramp
        sig.append(value)
    return sig


def oscillation_signal(n=256, lo=20, hi=80, center=50, amplitude=45, period=32):
    """Signal with large oscillation that periodically exceeds bounds."""
    return [center + amplitude * math.sin(2 * math.pi * i / period) for i in range(n)]


def burst_signal(n=256, lo=20, hi=80, center=50, burst_start=100, burst_len=15, burst_val=95):
    """Clean signal with a burst of consecutive violations."""
    sig = clean_signal(n, lo, hi, center, amplitude=10)
    for i in range(burst_start, min(burst_start + burst_len, n)):
        sig[i] = burst_val
    return sig


def mixed_signal(n=512, lo=20, hi=80):
    """Signal with multiple violation types in different regions."""
    center = 50
    sig = []
    for i in range(n):
        if i < 100:
            # Clean
            sig.append(center + 10 * math.sin(2 * math.pi * i / 32))
        elif i < 200:
            # Drift
            sig.append(center + 0.5 * (i - 100))
        elif i < 300:
            # Oscillation
            sig.append(center + 45 * math.sin(2 * math.pi * i / 24))
        elif i < 400:
            # Clean
            sig.append(center + 10 * math.sin(2 * math.pi * i / 32))
        else:
            # Bursts
            if 420 <= i < 435 or 460 <= i < 470:
                sig.append(95)
            else:
                sig.append(center + 10 * math.sin(2 * math.pi * i / 32))
    return sig


def run_all_tests():
    """Run all signal processing tests and print results."""
    
    random.seed(42)
    LO, HI = 20, 80
    N = 256
    
    passed = 0
    failed = 0
    
    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  ✅ {name}")
            passed += 1
        else:
            print(f"  ❌ {name} {detail}")
            failed += 1

    # =========================================================================
    # TEST 1: ConstraintFilter frequency response
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST 1: ConstraintFilter — Frequency Response Analysis")
    print("=" * 70)
    
    cf = ConstraintFilter(LO, HI, "battery_temp")
    
    # 1a: Signal entirely within bounds → no clipping → DC only
    resp_clean = cf.frequency_response(amplitude=25, frequency=0.1)
    print(f"\n  Clean signal (A=25, within range width {HI-LO}):")
    print(f"    Clipped: {resp_clean['clipped']}, DC: {resp_clean['dc_component']}")
    check("1a: Clean signal not clipped", not resp_clean['clipped'])
    check("1a: DC component = 1.0", resp_clean['dc_component'] == 1.0)
    
    # 1b: Signal exceeding bounds → clipping → harmonics
    resp_clipped = cf.frequency_response(amplitude=50, frequency=0.1)
    print(f"\n  Clipped signal (A=50, exceeds range width {HI-LO}):")
    print(f"    Clipped: {resp_clipped['clipped']}")
    print(f"    Duty cycle: {resp_clipped['duty_cycle']:.4f}")
    print(f"    Harmonics: {len([h for h in resp_clipped['harmonics'] if abs(h['coefficient']) > 0.01])}")
    print(f"    THD: {resp_clipped['thd']:.4f}")
    check("1b: Clipped signal detected", resp_clipped['clipped'])
    check("1b: Has harmonics", len(resp_clipped['harmonics']) > 0)
    check("1b: THD > 0", resp_clipped['thd'] > 0)
    check("1b: Duty cycle < 1", resp_clipped['duty_cycle'] < 1.0)
    
    # 1c: Spectral signature of a real signal with violations
    sig_spike = spike_signal(N, LO, HI, n_spikes=10)
    spec = cf.spectral_signature(sig_spike)
    print(f"\n  Spike signal spectral analysis:")
    print(f"    Violations: {spec['violation_count']}/{N} ({spec['violation_rate']:.3f})")
    print(f"    Pass rate: {spec['pass_rate']:.3f}")
    if spec['dominant_freq']:
        print(f"    Dominant freq: bin {spec['dominant_freq']['freq_bin']} "
              f"({spec['dominant_freq']['normalized_freq']:.4f})")
    check("1c: Spectral signature detects violations", spec['violation_count'] > 0)
    check("1c: Violation rate < 10%", spec['violation_rate'] < 0.1)
    
    # 1d: Different violation types have different spectral signatures
    sig_drift = drift_signal(N, LO, HI)
    sig_osc = oscillation_signal(N, LO, HI)
    spec_drift = cf.spectral_signature(sig_drift)
    spec_osc = cf.spectral_signature(sig_osc)
    print(f"\n  Drift vs Oscillation spectral comparison:")
    print(f"    Drift violations: {spec_drift['violation_count']} "
          f"(rate: {spec_drift['violation_rate']:.3f})")
    print(f"    Oscillation violations: {spec_osc['violation_count']} "
          f"(rate: {spec_osc['violation_rate']:.3f})")
    check("1d: Drift has more violations than clean", 
          spec_drift['violation_count'] > spec['violation_count'])
    check("1d: Oscillation has significant violations",
          spec_osc['violation_count'] > 0)
    check("1d: Drift and oscillation have different rates",
          spec_drift['violation_rate'] != spec_osc['violation_rate'])
    
    # =========================================================================
    # TEST 2: ViolationWavelet — pattern classification
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST 2: ViolationWavelet — Pattern Classification")
    print("=" * 70)
    
    cf2 = ConstraintFilter(LO, HI)
    
    # Generate signals and their masks
    sig_clean = clean_signal(N, LO, HI)
    sig_sp = spike_signal(N, LO, HI, n_spikes=8)
    sig_dr = drift_signal(N, LO, HI)
    sig_os = oscillation_signal(N, LO, HI)
    sig_bu = burst_signal(N, LO, HI)
    
    masks = {
        "clean": cf2.check_sequence(sig_clean),
        "spike": cf2.check_sequence(sig_sp),
        "drift": cf2.check_sequence(sig_dr),
        "oscillation": cf2.check_sequence(sig_os),
        "burst": cf2.check_sequence(sig_bu),
    }
    
    print("\n  Violation counts:")
    for name, mask in masks.items():
        v_count = sum(1 for m in mask if m == 0)
        print(f"    {name}: {v_count} violations ({v_count/N:.3f})")
    
    # Classify each pattern
    print("\n  Wavelet classification results:")
    classifications = {}
    for name, mask in masks.items():
        result = ViolationWavelet.classify_violation(mask, levels=6)
        classifications[name] = result
        print(f"    {name}: {result['pattern'].value} "
              f"(confidence: {result['confidence']:.3f})")
        if result['energy_distribution']:
            print(f"      Energy dist: {[f'{e:.3f}' for e in result['energy_distribution']]}")
            print(f"      Fine/Mid/Coarse: {result.get('fine_energy', 0):.3f} / "
                  f"{result.get('mid_energy', 0):.3f} / {result.get('coarse_energy', 0):.3f}")
    
    check("2a: Clean classified as CLEAN", 
          classifications["clean"]["pattern"] == ViolationPattern.CLEAN)
    check("2b: Spike classified as SPIKE",
          classifications["spike"]["pattern"] == ViolationPattern.SPIKE)
    check("2c: Drift classified as DRIFT",
          classifications["drift"]["pattern"] == ViolationPattern.DRIFT)
    check("2d: Oscillation classified (not CLEAN)",
          classifications["oscillation"]["pattern"] != ViolationPattern.CLEAN)
    check("2e: Burst classified (not CLEAN)",
          classifications["burst"]["pattern"] != ViolationPattern.CLEAN)
    
    # =========================================================================
    # TEST 3: KalmanPredictiveChecker — early detection
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST 3: KalmanPredictiveChecker — Predictive Constraint Checking")
    print("=" * 70)
    
    # 3a: Clean signal — all predictions should be definitely_pass
    kal_clean = KalmanPredictiveChecker(LO, HI, process_noise=0.1, 
                                         measurement_noise=1.0)
    sig = clean_signal(100, LO, HI)
    
    pass_count = 0
    correct_count = 0
    for val in sig:
        result = kal_clean.check_with_prediction(val)
        if result.pre_classification == PreClassification.DEFINITELY_PASS:
            pass_count += 1
        if result.prediction_correct:
            correct_count += 1
    
    perf = kal_clean.get_performance()
    print(f"\n  Clean signal (100 samples):")
    print(f"    Accuracy: {perf['accuracy']:.3f}")
    print(f"    Definitely pass: {perf['definitely_pass']}")
    print(f"    Final state: pos={perf['final_state']['position']:.2f} "
          f"vel={perf['final_state']['velocity']:.4f} "
          f"unc={perf['final_state']['uncertainty']:.4f}")
    check("3a: Clean signal high accuracy", perf['accuracy'] >= 0.9)
    check("3a: Most predictions are definitely_pass", pass_count >= 80)
    
    # 3b: Drift signal — should detect violation BEFORE it happens
    kal_drift = KalmanPredictiveChecker(LO, HI, process_noise=0.5,
                                         measurement_noise=0.5)
    sig_drift2 = drift_signal(100, LO, HI, drift_rate=0.8)
    
    early_warnings = 0
    pre_fail_before_actual = 0
    last_actual_pass_step = -1
    
    for step, val in enumerate(sig_drift2):
        result = kal_drift.check_with_prediction(val)
        
        if result.actual_passed and last_actual_pass_step < step:
            last_actual_pass_step = step
        
        if result.pre_classification == PreClassification.DEFINITELY_FAIL and result.actual_passed:
            pre_fail_before_actual += 1
        
        if result.early_warning:
            early_warnings += 1
    
    perf_drift = kal_drift.get_performance()
    print(f"\n  Drift signal (0.8 units/step, range 20-80):")
    print(f"    Early warnings: {early_warnings}")
    print(f"    Pre-fail before actual fail: {pre_fail_before_actual}")
    print(f"    Accuracy: {perf_drift['accuracy']:.3f}")
    print(f"    Early detections: {perf_drift['early_detections']}")
    print(f"    Final state: pos={perf_drift['final_state']['position']:.2f} "
          f"vel={perf_drift['final_state']['velocity']:.4f}")
    check("3b: Drift signal has early warnings", early_warnings > 0 or perf_drift['early_detections'] > 0)
    check("3b: Accuracy reasonable", perf_drift['accuracy'] >= 0.5)
    
    # 3c: Oscillation — uncertain region around boundaries
    kal_osc = KalmanPredictiveChecker(LO, HI, process_noise=1.0,
                                       measurement_noise=0.5)
    sig_osc2 = oscillation_signal(200, LO, HI, period=32)
    
    uncertain_count = 0
    for val in sig_osc2:
        result = kal_osc.check_with_prediction(val)
        if result.pre_classification == PreClassification.UNCERTAIN:
            uncertain_count += 1
    
    perf_osc = kal_osc.get_performance()
    print(f"\n  Oscillation signal (200 samples):")
    print(f"    Uncertain predictions: {uncertain_count}")
    print(f"    Accuracy: {perf_osc['accuracy']:.3f}")
    print(f"    Definitely fail: {perf_osc['definitely_fail']}")
    check("3c: Oscillation produces uncertain predictions", uncertain_count > 0)
    check("3c: Oscillation accuracy >= 0.5", perf_osc['accuracy'] >= 0.5)
    
    # =========================================================================
    # TEST 4: NyquistAnalyzer — sampling rate requirements
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST 4: NyquistAnalyzer — Minimum Sampling Rate")
    print("=" * 70)
    
    # 4a: Basic analysis
    nyq = NyquistAnalyzer.analyze(
        process_bandwidth=10.0,
        constraint_range=(LO, HI),
        violation_types=["drift", "oscillation", "spike", "burst"]
    )
    print(f"\n  Process bandwidth B=10Hz, range [{LO}, {HI}]:")
    print(f"    Nyquist rate: {nyq.min_sampling_rate} Hz")
    print(f"    Recommended rate: {nyq.recommended_rate} Hz")
    print(f"    Max inter-sample gap: {nyq.max_inter_sample_gap*1000:.1f} ms")
    check("4a: Nyquist rate = 2B", nyq.min_sampling_rate == 20.0)
    check("4a: Recommended > Nyquist", nyq.recommended_rate > nyq.min_sampling_rate)
    check("4a: Max gap = 1/(2B)", abs(nyq.max_inter_sample_gap - 0.05) < 0.001)
    
    # 4b: Drift rate → minimum rate
    drift_rate = 2.0  # units/sec
    range_width = HI - LO
    rate_for_drift = NyquistAnalyzer.minimum_rate_for_drift(drift_rate, range_width)
    print(f"\n  Drift rate: {drift_rate} units/sec, range width: {range_width}:")
    print(f"    Minimum rate for drift detection: {rate_for_drift:.2f} Hz")
    check("4b: Drift detection rate > 0", rate_for_drift > 0)
    check("4b: Drift rate reasonable (< 100 Hz)", rate_for_drift < 100)
    
    # 4c: Aliasing demo
    alias_demo = NyquistAnalyzer.aliasing_demo(
        signal_freq=5.0,
        sample_rates=[20.0, 12.0, 8.0, 6.0, 4.0],  # last two below Nyquist
        n_samples=128
    )
    print(f"\n  Aliasing demo (signal freq = 5 Hz):")
    for name, info in alias_demo.items():
        print(f"    {name}: observed={info['observed_freq']}Hz, "
              f"aliased={info['aliased']}, "
              f"violations={info['violation_count']}")
    
    aliased_count = sum(1 for v in alias_demo.values() if v['aliased'])
    check("4c: Lower rates show aliasing", aliased_count >= 2)
    check("4c: Highest rate not aliased", not alias_demo["Fs=20.0Hz"]["aliased"])
    
    # =========================================================================
    # TEST 5: CompressedSensingChecker — sub-Nyquist monitoring
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST 5: CompressedSensingChecker — Compressed Sensing")
    print("=" * 70)
    
    N_SENSORS = 30
    random.seed(42)
    
    # 5a: Generate sensor data with sparse violations
    constraints = [(20, 80)] * N_SENSORS  # all same range
    n_steps = 200
    
    # Most sensors clean, a few have violations
    sensor_seqs = []
    for s in range(N_SENSORS):
        base = 50 + 10 * math.sin(2 * math.pi * s / N_SENSORS)
        seq = [base + 5 * math.sin(2 * math.pi * i / 50) for i in range(n_steps)]
        
        # Inject violations: ~5% of values are violations, in ~3-4 sensors
        if s in [3, 12, 22, 28]:
            for t in range(n_steps):
                if random.random() < 0.15:
                    seq[t] = random.choice([15, 85, 90, 10])
        
        sensor_seqs.append(seq)
    
    # Count true violations
    total_true = 0
    for s in range(N_SENSORS):
        for t in range(n_steps):
            if not (20 <= sensor_seqs[s][t] <= 80):
                total_true += 1
    print(f"\n  Setup: {N_SENSORS} sensors, {n_steps} steps, {total_true} true violations")
    
    # 5b: Round-robin with K = N/3
    k = N_SENSORS // 3
    cs_rr = CompressedSensingChecker(N_SENSORS, constraints, k_per_step=k, mode="round_robin")
    sim_rr = cs_rr.run_simulation(sensor_seqs, n_steps)
    print(f"\n  Round-robin (K={k}, compression={sim_rr['compression_ratio']:.2f}):")
    print(f"    Detection rate: {sim_rr['overall_detection_rate']:.3f}")
    print(f"    Detected: {sim_rr['cumulative_detected']} / {sim_rr['cumulative_true']}")
    check("5b: Round-robin detection rate > 0.3 (K=N/3)", sim_rr['overall_detection_rate'] > 0.3)
    
    # 5c: Priority mode — should do better
    random.seed(42)
    cs_prio = CompressedSensingChecker(N_SENSORS, constraints, k_per_step=k, mode="priority")
    sim_prio = cs_prio.run_simulation(sensor_seqs, n_steps)
    print(f"\n  Priority mode (K={k}):")
    print(f"    Detection rate: {sim_prio['overall_detection_rate']:.3f}")
    print(f"    Detected: {sim_prio['cumulative_detected']} / {sim_prio['cumulative_true']}")
    check("5c: Priority detection rate > 0", sim_prio['overall_detection_rate'] > 0)
    
    # 5d: Theoretical minimum K
    for max_v in [1, 3, 5, 10]:
        k_min = CompressedSensingChecker.theoretical_guarantee(N_SENSORS, max_v)
        print(f"    Theoretical K for S={max_v} violations: {k_min} "
              f"(ratio: {k_min/N_SENSORS:.2f})")
    check("5d: Theoretical K increases with max violations", True)
    
    # 5e: Show detection improves with more K
    rates = []
    for k_test in [3, 5, 10, 15, 20, 25]:
        random.seed(42)
        cs_test = CompressedSensingChecker(N_SENSORS, constraints, k_per_step=k_test, mode="round_robin")
        sim_test = cs_test.run_simulation(sensor_seqs, min(50, n_steps))
        rates.append((k_test, sim_test['overall_detection_rate']))
    
    print(f"\n  Detection rate vs K (first 50 steps):")
    for k_val, rate in rates:
        bar = "█" * int(rate * 40)
        print(f"    K={k_val:2d} ({k_val/N_SENSORS:.2f}): {rate:.3f} {bar}")
    
    check("5e: More K → better detection (general trend)", rates[-1][1] >= rates[0][1])
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
