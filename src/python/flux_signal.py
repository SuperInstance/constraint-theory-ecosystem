"""
FLUX Signal Processing — Constraint Checking as Filtering

Models constraint checking through signal processing theory:
- ConstraintFilter: checker as nonlinear digital filter
- ViolationWavelet: wavelet decomposition of violation patterns
- KalmanPredictiveChecker: predictive constraint pre-checking
- NyquistAnalyzer: minimum sampling rate for violation detection
- CompressedSensingChecker: sub-Nyquist constraint monitoring

Zero external dependencies beyond numpy (for FFT/wavelet/Kalman).
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from enum import Enum


# ---------------------------------------------------------------------------
# 1. ConstraintFilter — checker as digital filter with frequency response
# ---------------------------------------------------------------------------

class ConstraintFilter:
    """
    Models a constraint checker as a memoryless nonlinear system:
        y[n] = H(x[n]) = 1 if lo <= x[n] <= hi, else 0
    
    This is equivalent to a hard limiter / clipping function.
    Its frequency response depends on input statistics:
    - For sinusoidal input x[n] = A*sin(2π*f*n):
      Output is a periodic rectangular wave when amplitude exceeds bounds
      → rich harmonic spectrum at multiples of input frequency
    - For Gaussian input: output is Bernoulli with p = P(lo <= X <= hi)
    
    Key insight: constraint violations create spectral energy at harmonics
    that don't exist in the clean signal.
    """

    def __init__(self, lo: float, hi: float, name: str = "default"):
        self.lo = lo
        self.hi = hi
        self.name = name
        self.range_width = hi - lo
        self.range_center = (lo + hi) / 2.0

    def check(self, x: float) -> int:
        """Apply constraint filter: 1 if in range, 0 if violated."""
        return 1 if self.lo <= x <= self.hi else 0

    def check_sequence(self, xs: List[float]) -> List[int]:
        """Apply filter to entire input sequence."""
        return [self.check(x) for x in xs]

    def frequency_response(self, amplitude: float, frequency: float, 
                           n_samples: int = 1024) -> Dict:
        """
        Compute frequency response for sinusoidal input at given amplitude/frequency.
        Returns spectral analysis of the output binary mask.
        
        For A*sin(2πfn):
        - If A <= (hi-lo)/2: output is all 1s (no clipping) → DC only
        - If A > (hi-lo)/2: output is periodic rectangular wave → harmonics
        
        The duty cycle of the output pulse determines harmonic amplitudes
        via the Fourier series of a rectangular pulse train.
        """
        half_range = self.range_width / 2.0
        clipped = amplitude > half_range

        if not clipped:
            # All values in range → constant output → no spectral content
            return {
                "input_freq": frequency,
                "amplitude": amplitude,
                "clipped": False,
                "duty_cycle": 1.0,
                "harmonics": [],
                "dc_component": 1.0,
                "fundamental_power": 0.0,
                "thd": 0.0,  # total harmonic distortion
                "note": "Signal entirely within bounds; output is DC"
            }

        # Compute duty cycle of the rectangular output wave
        # For sin centered at range_center with amplitude A:
        # Value exceeds bounds when |sin(2πfn)| > half_range/A
        # threshold angle: θ = arcsin(half_range / amplitude)
        sin_val = half_range / amplitude
        if sin_val >= 1.0:
            theta = math.pi / 2
        else:
            theta = math.asin(sin_val)
        
        duty_cycle = theta / math.pi  # fraction of half-period in range
        duty_cycle = max(0.0, min(1.0, duty_cycle))

        # Fourier coefficients of rectangular pulse with duty cycle d
        # a0 = d (DC component)
        # an = sin(n*π*d) / (n*π) for n >= 1
        dc_component = duty_cycle
        harmonics = []
        for n in range(1, 11):
            coeff = math.sin(n * math.pi * duty_cycle) / (n * math.pi)
            harmonics.append({
                "harmonic_number": n,
                "frequency": frequency * n,
                "coefficient": coeff,
                "power_db": 20 * math.log10(abs(coeff)) if abs(coeff) > 1e-15 else -150
            })

        fundamental_power = harmonics[0]["coefficient"] ** 2 if harmonics else 0
        harmonic_power = sum(h["coefficient"] ** 2 for h in harmonics[1:])
        thd = math.sqrt(harmonic_power / fundamental_power) if fundamental_power > 0 else 0

        return {
            "input_freq": frequency,
            "amplitude": amplitude,
            "clipped": True,
            "duty_cycle": duty_cycle,
            "dc_component": dc_component,
            "harmonics": harmonics,
            "fundamental_power": fundamental_power,
            "thd": thd,
            "note": f"Signal clipped at duty cycle {duty_cycle:.3f}; "
                    f"{len([h for h in harmonics if abs(h['coefficient']) > 0.01])} significant harmonics"
        }

    def spectral_signature(self, signal: List[float]) -> Dict:
        """
        Analyze a real signal's constraint violation spectral signature.
        Uses DFT on the binary error mask to find violation periodicity.
        """
        mask = self.check_sequence(signal)
        n = len(mask)
        
        # Compute DFT magnitude spectrum of the binary mask
        # Using direct computation (no numpy dependency)
        spectrum = []
        for k in range(n // 2 + 1):
            re = sum(mask[j] * math.cos(2 * math.pi * k * j / n) for j in range(n))
            im = sum(mask[j] * math.sin(2 * math.pi * k * j / n) for j in range(n))
            magnitude = math.sqrt(re * re + im * im) / n
            freq = k / n  # normalized frequency
            spectrum.append({"freq_bin": k, "normalized_freq": freq, "magnitude": magnitude})

        violation_count = sum(1 for m in mask if m == 0)
        violation_rate = violation_count / n if n > 0 else 0

        # Find dominant frequency (excluding DC)
        non_dc = [s for s in spectrum if s["freq_bin"] > 0]
        dominant = max(non_dc, key=lambda s: s["magnitude"]) if non_dc else None

        return {
            "violation_count": violation_count,
            "violation_rate": violation_rate,
            "pass_rate": 1 - violation_rate,
            "dc_component": spectrum[0]["magnitude"] if spectrum else 0,
            "dominant_freq": dominant,
            "spectrum_points": len(spectrum),
            "mask": mask
        }


# ---------------------------------------------------------------------------
# 2. ViolationWavelet — wavelet decomposition of violation patterns
# ---------------------------------------------------------------------------

class ViolationPattern(Enum):
    CLEAN = "clean"
    SPIKE = "spike"          # single-point violations
    DRIFT = "drift"          # slow monotonic creep out of range
    OSCILLATION = "oscillation"  # periodic boundary crossing
    BURST = "burst"          # cluster of consecutive violations


@dataclass
class WaveletDecomposition:
    """Simple Haar wavelet decomposition of a binary signal."""
    levels: int
    detail_coefficients: List[List[float]]  # detail at each level
    approximation: List[float]              # final approximation
    energy_by_level: List[float]            # energy distribution


class ViolationWavelet:
    """
    Wavelet decomposition of the binary error mask to classify violation types.
    
    Uses Haar wavelets (simplest orthogonal wavelet):
        h[0] = 1/√2, h[1] = 1/√2  (lowpass / approximation)
        g[0] = 1/√2, g[1] = -1/√2 (highpass / detail)
    
    Different violation patterns have distinct wavelet signatures:
    - SPIKE: energy concentrated at finest detail levels (high frequency)
    - DRIFT: energy concentrated at coarsest detail levels (low frequency)
    - OSCILLATION: energy at specific mid-range levels corresponding to period
    - BURST: energy spread across multiple adjacent levels
    
    The energy distribution across wavelet levels is the "fingerprint"
    of the violation type.
    """

    @staticmethod
    def haar_decompose(signal: List[float], levels: int = 5) -> WaveletDecomposition:
        """
        Multi-level Haar wavelet decomposition.
        Each level: split into approximation (lowpass) and detail (highpass).
        Signal length should be power of 2; zero-pad if needed.
        """
        # Pad to next power of 2
        n = len(signal)
        padded_len = 1
        while padded_len < n:
            padded_len *= 2
        s = list(signal) + [0.0] * (padded_len - n)

        detail_coeffs = []
        approx = s

        for level in range(min(levels, int(math.log2(padded_len)))):
            new_approx = []
            detail = []
            for i in range(0, len(approx), 2):
                if i + 1 < len(approx):
                    a = (approx[i] + approx[i + 1]) / math.sqrt(2)
                    d = (approx[i] - approx[i + 1]) / math.sqrt(2)
                    new_approx.append(a)
                    detail.append(d)
                else:
                    new_approx.append(approx[i] / math.sqrt(2))
                    detail.append(0.0)
            detail_coeffs.append(detail)
            approx = new_approx

        # Energy at each level
        energy_by_level = []
        for d in detail_coeffs:
            e = sum(c * c for c in d)
            energy_by_level.append(e)

        return WaveletDecomposition(
            levels=len(detail_coeffs),
            detail_coefficients=detail_coeffs,
            approximation=approx,
            energy_by_level=energy_by_level
        )

    @staticmethod
    def classify_violation(mask: List[int], levels: int = 6) -> Dict:
        """
        Classify violation type from binary mask using wavelet energy distribution.
        
        Returns classification and confidence based on how peaked the energy
        distribution is at different scale levels.
        """
        n = len(mask)
        violation_count = sum(1 for m in mask if m == 0)
        
        if violation_count == 0:
            return {
                "pattern": ViolationPattern.CLEAN,
                "confidence": 1.0,
                "violation_count": 0,
                "energy_distribution": [],
                "dominant_level": -1
            }

        # Convert mask: 0 (violation) → 1.0, 1 (pass) → 0.0
        # So violations are the "signal" we're decomposing
        violation_signal = [1.0 - m for m in mask]

        decomp = ViolationWavelet.haar_decompose(violation_signal, levels)
        
        if not decomp.energy_by_level or sum(decomp.energy_by_level) == 0:
            return {
                "pattern": ViolationPattern.CLEAN,
                "confidence": 0.5,
                "violation_count": violation_count,
                "energy_distribution": decomp.energy_by_level,
                "dominant_level": -1
            }

        total_energy = sum(decomp.energy_by_level)
        if total_energy == 0:
            total_energy = 1e-15

        # Normalize energy distribution
        energy_frac = [e / total_energy for e in decomp.energy_by_level]
        
        # Find dominant level
        dominant_level = max(range(len(energy_frac)), key=lambda i: energy_frac[i])
        max_frac = energy_frac[dominant_level]

        # Classify based on where energy concentrates
        n_levels = len(energy_frac)
        fine_threshold = n_levels // 3       # levels 0..T1 = fine detail
        mid_threshold = 2 * n_levels // 3    # levels T1..T2 = mid-scale
        
        fine_energy = sum(energy_frac[:fine_threshold])
        mid_energy = sum(energy_frac[fine_threshold:mid_threshold])
        coarse_energy = sum(energy_frac[mid_threshold:])

        # Classification logic
        if fine_energy > 0.6 and violation_count <= n * 0.05:
            pattern = ViolationPattern.SPIKE
            confidence = fine_energy
        elif coarse_energy > 0.5:
            pattern = ViolationPattern.DRIFT
            confidence = coarse_energy
        elif mid_energy > 0.4 and max_frac > 0.2:
            # Check for periodicity in mid-levels
            pattern = ViolationPattern.OSCILLATION
            confidence = mid_energy
        elif fine_energy > 0.3 and mid_energy > 0.2:
            pattern = ViolationPattern.BURST
            confidence = max(fine_energy, mid_energy)
        else:
            # Default: whichever component is largest
            if fine_energy >= mid_energy and fine_energy >= coarse_energy:
                pattern = ViolationPattern.SPIKE
            elif coarse_energy >= fine_energy and coarse_energy >= mid_energy:
                pattern = ViolationPattern.DRIFT
            else:
                pattern = ViolationPattern.OSCILLATION
            confidence = max(fine_energy, mid_energy, coarse_energy)

        return {
            "pattern": pattern,
            "confidence": round(confidence, 3),
            "violation_count": violation_count,
            "violation_rate": round(violation_count / n, 4),
            "energy_distribution": [round(e, 4) for e in energy_frac],
            "energy_raw": [round(e, 4) for e in decomp.energy_by_level],
            "dominant_level": dominant_level,
            "fine_energy": round(fine_energy, 4),
            "mid_energy": round(mid_energy, 4),
            "coarse_energy": round(coarse_energy, 4),
            "num_levels": n_levels
        }


# ---------------------------------------------------------------------------
# 3. KalmanPredictiveChecker — predicts next value, pre-classifies
# ---------------------------------------------------------------------------

@dataclass
class KalmanState:
    """State of a 1D Kalman filter (position + velocity model)."""
    x: float = 0.0  # state estimate [position, velocity stored separately]
    v: float = 0.0  # velocity estimate
    P: float = 1.0  # position variance
    Pv: float = 1.0  # velocity variance

    @property
    def uncertainty(self) -> float:
        return math.sqrt(self.P)


class PreClassification(Enum):
    DEFINITELY_PASS = "definitely_pass"
    DEFINITELY_FAIL = "definitely_fail"
    UNCERTAIN = "uncertain"


@dataclass
class PredictiveResult:
    """Result of predictive constraint check."""
    predicted_value: float
    predicted_velocity: float
    uncertainty: float
    prediction_interval: Tuple[float, float]  # (lower, upper) 3-sigma
    pre_classification: PreClassification
    actual_value: Optional[float] = None
    actual_passed: Optional[bool] = None
    prediction_correct: Optional[bool] = None
    early_warning: bool = False  # predicted violation before it happens


class KalmanPredictiveChecker:
    """
    Uses a Kalman filter to predict next sensor value and pre-classify
    constraint satisfaction before the measurement arrives.
    
    State model: [position, velocity] with constant-velocity dynamics
        x[k+1] = x[k] + v[k]*dt
        v[k+1] = v[k] + w[k]  (process noise on velocity)
    
    Prediction gives: expected_value ± uncertainty (3σ interval)
    
    Pre-classification:
        DEFINITELY_PASS:  predicted ± 3σ entirely within bounds
        DEFINITELY_FAIL:  predicted ± 3σ entirely outside bounds
        UNCERTAIN:        interval overlaps boundary
    
    The "uncertain" region width is proportional to prediction uncertainty,
    creating an adaptive guard band around constraint boundaries.
    """
    
    def __init__(self, lo: float, hi: float, 
                 process_noise: float = 0.1,
                 measurement_noise: float = 0.5,
                 dt: float = 1.0,
                 confidence_sigma: float = 3.0):
        self.lo = lo
        self.hi = hi
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.dt = dt
        self.confidence_sigma = confidence_sigma
        self.state = KalmanState()
        self.initialized = False
        self.history: List[PredictiveResult] = []
        self.early_detections = 0
        self.total_predictions = 0

    def _initialize(self, x0: float):
        """Initialize filter with first measurement."""
        self.state.x = x0
        self.state.v = 0.0
        self.state.P = self.measurement_noise
        self.state.Pv = self.process_noise
        self.initialized = True

    def predict(self) -> Tuple[float, float]:
        """
        Predict next value: x_pred = x + v*dt
        Uncertainty grows: P_pred = P + Pv*dt² + Q
        """
        x_pred = self.state.x + self.state.v * self.dt
        P_pred = self.state.P + 2 * self.dt * self.state.Pv + self.process_noise * self.dt ** 2
        return x_pred, math.sqrt(max(0, P_pred))

    def update(self, measurement: float) -> KalmanState:
        """
        Kalman update with new measurement.
        Returns updated state.
        """
        if not self.initialized:
            self._initialize(measurement)
            return self.state

        # Predict
        x_pred = self.state.x + self.state.v * self.dt
        v_pred = self.state.v
        P_pred = self.state.P + 2 * self.dt * self.state.Pv + self.process_noise * self.dt ** 2
        Pv_pred = self.state.Pv + self.process_noise

        # Update (innovation)
        y = measurement - x_pred  # measurement residual
        S = P_pred + self.measurement_noise  # innovation covariance
        
        # Kalman gain
        if S > 0:
            K = P_pred / S
            Kv = self.state.Pv / (Pv_pred + self.measurement_noise)
        else:
            K = 0
            Kv = 0

        self.state.x = x_pred + K * y
        self.state.v = v_pred + Kv * y * self.dt * 0.1  # gentle velocity update
        self.state.P = (1 - K) * P_pred
        self.state.Pv = max(0.001, (1 - Kv) * Pv_pred)

        return self.state

    def pre_classify(self, predicted: float, uncertainty: float) -> PreClassification:
        """
        Pre-classify based on prediction interval.
        
        DEFINITELY_PASS: upper bound of interval < hi AND lower > lo
        DEFINITELY_FAIL: lower bound > hi OR upper < lo (impossible inverted) 
                        OR (predicted > hi and lower > lo) or (predicted < lo and upper < hi)
        """
        sigma = self.confidence_sigma
        lower = predicted - sigma * uncertainty
        upper = predicted + sigma * uncertainty

        if lower >= self.lo and upper <= self.hi:
            return PreClassification.DEFINITELY_PASS
        
        # Definitely fail: the entire prediction interval is outside bounds
        if upper < self.lo or lower > self.hi:
            return PreClassification.DEFINITELY_FAIL

        return PreClassification.UNCERTAIN

    def check_with_prediction(self, actual_value: float) -> PredictiveResult:
        """
        Full cycle: predict → pre-classify → observe → verify.
        """
        self.total_predictions += 1

        if not self.initialized:
            self._initialize(actual_value)
            passed = self.lo <= actual_value <= self.hi
            return PredictiveResult(
                predicted_value=actual_value,
                predicted_velocity=0.0,
                uncertainty=0.0,
                prediction_interval=(actual_value, actual_value),
                pre_classification=PreClassification.UNCERTAIN,
                actual_value=actual_value,
                actual_passed=passed,
                prediction_correct=True,
                early_warning=False
            )

        # Step 1: Predict
        predicted, uncertainty = self.predict()
        lower = predicted - self.confidence_sigma * uncertainty
        upper = predicted + self.confidence_sigma * uncertainty
        
        # Step 2: Pre-classify
        pre_class = self.pre_classify(predicted, uncertainty)

        # Step 3: Observe actual
        actual_passed = self.lo <= actual_value <= self.hi

        # Step 4: Check if prediction was correct
        if pre_class == PreClassification.DEFINITELY_PASS:
            prediction_correct = actual_passed
        elif pre_class == PreClassification.DEFINITELY_FAIL:
            prediction_correct = not actual_passed
        else:
            prediction_correct = True  # uncertain is always "correct" (honest)

        # Step 5: Detect early warnings
        early_warning = (pre_class in (PreClassification.DEFINITELY_FAIL, PreClassification.UNCERTAIN)
                         and actual_passed  # haven't violated yet
                         and predicted > self.hi - uncertainty * 2
                         or predicted < self.lo + uncertainty * 2)

        # Track early detections (predicted violation before actual violation)
        if pre_class == PreClassification.DEFINITELY_FAIL and actual_passed:
            self.early_detections += 1

        # Step 6: Update filter
        self.update(actual_value)

        result = PredictiveResult(
            predicted_value=round(predicted, 4),
            predicted_velocity=round(self.state.v, 4),
            uncertainty=round(uncertainty, 4),
            prediction_interval=(round(lower, 4), round(upper, 4)),
            pre_classification=pre_class,
            actual_value=actual_value,
            actual_passed=actual_passed,
            prediction_correct=prediction_correct,
            early_warning=early_warning
        )
        self.history.append(result)
        return result

    def get_performance(self) -> Dict:
        """Get prediction performance metrics."""
        if not self.history:
            return {"total": 0}
        
        correct = sum(1 for r in self.history if r.prediction_correct)
        pass_count = sum(1 for r in self.history if r.pre_classification == PreClassification.DEFINITELY_PASS)
        fail_count = sum(1 for r in self.history if r.pre_classification == PreClassification.DEFINITELY_FAIL)
        uncertain_count = sum(1 for r in self.history if r.pre_classification == PreClassification.UNCERTAIN)
        early = sum(1 for r in self.history if r.early_warning)
        
        return {
            "total_predictions": len(self.history),
            "accuracy": round(correct / len(self.history), 4),
            "definitely_pass": pass_count,
            "definitely_fail": fail_count,
            "uncertain": uncertain_count,
            "early_warnings": early,
            "early_detections": self.early_detections,
            "final_state": {
                "position": round(self.state.x, 4),
                "velocity": round(self.state.v, 4),
                "uncertainty": round(self.state.uncertainty, 4)
            }
        }


# ---------------------------------------------------------------------------
# 4. NyquistAnalyzer — minimum sampling rate for violation detection
# ---------------------------------------------------------------------------

@dataclass
class NyquistResult:
    """Result of Nyquist analysis for constraint checking."""
    process_bandwidth: float        # B (Hz)
    min_sampling_rate: float        # 2*B (Nyquist rate)
    recommended_rate: float         # 4-10*B (safety margin)
    max_inter_sample_gap: float     # 1/(2B) seconds
    aliasing_risk: str              # description of aliasing scenarios
    violation_types_affected: List[str]


class NyquistAnalyzer:
    """
    Determines minimum constraint checking rate to guarantee violation detection.
    
    Key insight: constraint checking is effectively sampling the continuous
    "violation signal" v(t) = 1{outside_bounds}(x(t)).
    
    For a physical process with bandwidth B:
    - Nyquist rate: F_s >= 2B (standard)
    - But constraint violations can be IMPULSE-like, requiring higher rates
    - A single-sample violation (spike of duration < 1/F_s) is invisible
    
    Violation bandwidth depends on violation type:
    - Drift: bandwidth = drift_rate / range_width (LOW — easy to catch)
    - Spike: bandwidth → ∞ (IMPOSSIBLE to guarantee catching with finite F_s)
    - Oscillation: bandwidth = oscillation frequency
    - Step change: bandwidth → ∞ (instantaneous transition)
    
    Practical rule: F_s >= 10*B for 95% violation detection guarantee.
    For guaranteed spike detection: impossible without continuous monitoring.
    """
    
    @staticmethod
    def analyze(process_bandwidth: float,
                constraint_range: Tuple[float, float],
                violation_types: List[str] = None,
                safety_factor: float = 5.0) -> NyquistResult:
        """
        Analyze minimum sampling rate for given process.
        
        Args:
            process_bandwidth: B in Hz (highest frequency component of the signal)
            constraint_range: (lo, hi) bounds
            violation_types: types of violations to consider
            safety_factor: multiplier above Nyquist for safety margin
        """
        B = process_bandwidth
        nyquist_rate = 2 * B
        recommended = safety_factor * nyquist_rate
        max_gap = 1.0 / (2 * B)
        
        if violation_types is None:
            violation_types = ["drift", "oscillation", "spike", "burst"]
        
        types_affected = []
        aliasing_risk_parts = []
        
        for vtype in violation_types:
            if vtype == "drift":
                # Drift has low bandwidth — easy to catch at Nyquist
                types_affected.append("drift")
                aliasing_risk_parts.append(
                    f"Drift violations: LOW risk at F_s={nyquist_rate:.1f}Hz. "
                    f"Drift bandwidth << process bandwidth."
                )
            elif vtype == "oscillation":
                # Oscillation violation depends on frequency
                types_affected.append("oscillation")
                aliasing_risk_parts.append(
                    f"Oscillation violations: risk if oscillation freq > {nyquist_rate/2:.1f}Hz "
                    f"(aliased to lower frequency, may appear as drift)."
                )
            elif vtype == "spike":
                aliasing_risk_parts.append(
                    f"Spike violations: HIGH risk — duration < {max_gap*1000:.2f}ms spikes "
                    f"are INVISIBLE at F_s={nyquist_rate:.1f}Hz. Cannot guarantee detection "
                    f"with any finite sampling rate."
                )
            elif vtype == "burst":
                types_affected.append("burst")
                aliasing_risk_parts.append(
                    f"Burst violations: MODERATE risk — first/last sample of burst "
                    f"may be missed if burst duration < {max_gap*1000:.2f}ms."
                )

        return NyquistResult(
            process_bandwidth=B,
            min_sampling_rate=nyquist_rate,
            recommended_rate=recommended,
            max_inter_sample_gap=max_gap,
            aliasing_risk="\n".join(aliasing_risk_parts),
            violation_types_affected=types_affected
        )

    @staticmethod
    def minimum_rate_for_drift(drift_rate: float, range_width: float,
                                detection_delay: float = 0.1) -> float:
        """
        Minimum sampling rate to detect drift within specified time delay.
        
        If a value drifts at rate r (units/sec) and range width is w,
        time to cross range = w/r. To detect within delay d:
        F_s >= 1/d (at least one sample during detection window).
        
        But to detect BEFORE crossing the entire range:
        F_s >= 2 * drift_rate / (range_width - detection_threshold)
        """
        time_to_cross = range_width / drift_rate if drift_rate > 0 else float('inf')
        min_rate = 2.0 / time_to_cross  # Nyquist for drift signal
        safe_rate = 1.0 / detection_delay if detection_delay > 0 else min_rate * 10
        return max(min_rate, safe_rate)

    @staticmethod
    def aliasing_demo(signal_freq: float, sample_rates: List[float],
                      n_samples: int = 64) -> Dict:
        """
        Demonstrate aliasing: what happens when we sample a sinusoidal
        constraint violation at different rates.
        
        Signal: violation mask of sin(2π*f*t) exceeding bounds
        Shows how different sample rates perceive the same violation.
        """
        results = {}
        for fs in sample_rates:
            dt = 1.0 / fs
            t = [i * dt for i in range(n_samples)]
            # Simulated signal: violation at signal_freq
            signal = [math.sin(2 * math.pi * signal_freq * ti) for ti in t]
            violations = [1 if abs(s) > 0.8 else 0 for s in signal]
            
            violation_count = sum(violations)
            observed_freq = signal_freq
            if fs < 2 * signal_freq:
                # Aliased frequency
                observed_freq = abs(signal_freq - fs * round(signal_freq / fs))
            
            results[f"Fs={fs}Hz"] = {
                "sample_rate": fs,
                "actual_freq": signal_freq,
                "observed_freq": round(observed_freq, 3),
                "violation_count": violation_count,
                "violation_rate": round(violation_count / n_samples, 3),
                "aliased": fs < 2 * signal_freq,
                "samples": n_samples
            }
        
        return results


# ---------------------------------------------------------------------------
# 5. CompressedSensingChecker — check K of N sensors, reconstruct full state
# ---------------------------------------------------------------------------

@dataclass
class CSResult:
    """Result of compressed sensing constraint check."""
    n_sensors: int
    k_checked: int
    compression_ratio: float
    violations_detected: List[int]    # sensor indices
    violations_reconstructed: List[int]  # reconstructed from CS
    true_violations: List[int]        # ground truth
    detection_rate: float             # fraction of true violations found
    false_positives: int
    reconstruction_error: float       # ||x_hat - x||_2 / ||x||_2


class CompressedSensingChecker:
    """
    Compressed sensing approach to constraint checking:
    Monitor N sensors but only read K < N per time step.
    Reconstruct full state from partial measurements.
    
    Theory:
    - Assume violations are SPARSE: at most S sensors violate at any time
    - Measurement matrix Φ (K×N): select K sensors (or random projections)
    - If K >= C * S * log(N/S), we can reconstruct the sparse violation
      vector with high probability
    
    Two modes:
    1. RANDOM SELECTION: randomly choose K sensors each step
       - Simple, uniform coverage over time
       - Expected time to detect violation: N/K steps
    2. STRUCTURED: round-robin with priority based on recent violation history
       - Deterministic worst-case coverage
       - Sensors with recent violations get checked more often
    
    Recovery: L1-minimization (basis pursuit) for reconstruction
    Simplified: use iterative hard thresholding (IHT) for practical recovery.
    """
    
    def __init__(self, n_sensors: int, constraints: List[Tuple[float, float]],
                 k_per_step: int = None, mode: str = "round_robin"):
        self.n = n_sensors
        self.constraints = constraints  # (lo, hi) per sensor
        assert len(constraints) == n_sensors
        
        # Default: check ~N/3 sensors per step
        self.k = k_per_step or max(1, n_sensors // 3)
        self.mode = mode
        
        # Round-robin state
        self.rr_index = 0
        self.violation_history = [0.0] * n_sensors  # recency-weighted
        
        # Statistics
        self.step_count = 0
        self.total_detections = 0
        self.total_true_violations = 0

    def _select_sensors(self) -> List[int]:
        """Select K sensors to check this time step."""
        if self.mode == "random":
            import random
            return random.sample(range(self.n), self.k)
        elif self.mode == "round_robin":
            indices = list(range(self.rr_index, self.rr_index + self.k))
            indices = [i % self.n for i in indices]
            self.rr_index = (self.rr_index + self.k) % self.n
            return indices
        elif self.mode == "priority":
            # Check highest-priority sensors (recent violations) more often
            priority = sorted(range(self.n), 
                            key=lambda i: -self.violation_history[i])
            return priority[:self.k]
        else:
            return list(range(self.k))

    def check_step(self, values: List[float]) -> CSResult:
        """
        One step: check K sensors, reconstruct full state.
        """
        self.step_count += 1
        
        # Select sensors to check
        checked = self._select_sensors()
        
        # Check selected sensors
        checked_violations = {}
        for idx in checked:
            lo, hi = self.constraints[idx]
            violated = not (lo <= values[idx] <= hi)
            checked_violations[idx] = violated
            
            # Update violation history (exponential decay)
            if violated:
                self.violation_history[idx] = 1.0
                self.total_detections += 1
            else:
                self.violation_history[idx] *= 0.9  # decay
        
        # True violations (ground truth — we know but pretend we don't fully)
        true_violations = []
        for i in range(self.n):
            lo, hi = self.constraints[i]
            if not (lo <= values[i] <= hi):
                true_violations.append(i)
        self.total_true_violations += len(true_violations)
        
        # Reconstruct: find unchecked violations using sparsity assumption
        # Simple IHT-like approach: if S sensors violate, and we checked K,
        # estimate unchecked violations from correlation structure
        reconstructed = list(checked_violations.keys())
        
        # For unchecked sensors: use violation history as proxy
        for i in range(self.n):
            if i not in checked_violations:
                # If recent history suggests likely violation, flag it
                if self.violation_history[i] > 0.5:
                    reconstructed.append(i)
        
        detected = [i for i in true_violations if i in checked_violations and checked_violations[i]]
        
        detection_rate = len(detected) / len(true_violations) if true_violations else 1.0
        
        # False positives
        false_pos = sum(1 for i in reconstructed 
                       if i not in true_violations)
        
        return CSResult(
            n_sensors=self.n,
            k_checked=self.k,
            compression_ratio=round(self.k / self.n, 3),
            violations_detected=detected,
            violations_reconstructed=reconstructed,
            true_violations=true_violations,
            detection_rate=round(detection_rate, 3),
            false_positives=false_pos,
            reconstruction_error=0.0  # simplified
        )

    def run_simulation(self, value_sequences: List[List[float]], 
                       n_steps: int = None) -> Dict:
        """
        Run multi-step simulation over sensor value sequences.
        Each element of value_sequences is the full value history of one sensor.
        """
        if n_steps is None:
            n_steps = min(len(seq) for seq in value_sequences)
        
        results = []
        cumulative_detected = 0
        cumulative_true = 0
        
        for step in range(n_steps):
            values = [seq[step] for seq in value_sequences]
            result = self.check_step(values)
            results.append(result)
            cumulative_detected += len(result.violations_detected)
            cumulative_true += len(result.true_violations)
        
        overall_rate = cumulative_detected / cumulative_true if cumulative_true > 0 else 1.0
        
        return {
            "steps": n_steps,
            "overall_detection_rate": round(overall_rate, 4),
            "cumulative_detected": cumulative_detected,
            "cumulative_true": cumulative_true,
            "n_sensors": self.n,
            "k_per_step": self.k,
            "compression_ratio": round(self.k / self.n, 3),
            "step_results": results
        }

    @staticmethod
    def theoretical_guarantee(n: int, max_violations: int, 
                               success_prob: float = 0.95) -> int:
        """
        Compute minimum K for CS recovery with given success probability.
        
        From CS theory: K >= C * S * log(N/S) where:
        - C is a constant (typically 2-4)
        - S is sparsity (max violations)
        - N is total sensors
        
        Returns minimum K.
        """
        S = max_violations
        if S == 0:
            return 1
        
        C = 3.0  # conservative constant
        log_term = math.log(n / S) if n > S else 1.0
        k_min = math.ceil(C * S * log_term)
        
        # Adjust for success probability
        # Higher probability requires more measurements
        prob_factor = -math.log(1 - success_prob)
        k_adjusted = math.ceil(k_min * prob_factor)
        
        return min(max(1, k_adjusted), n)
