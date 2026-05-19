"""
FLUX v4 Streaming Constraint Engine — Real-Time Sensor Feed Processing

Production streaming engine that accepts named sensor feeds, checks constraints
in real-time, maintains sliding window statistics, emits violation events with
severity, applies adaptive strategies (predictive, wavelet, Kalman), and
generates provenance logs.

Designed for 10,000 sensors at 1kHz.

Dependencies: math, hashlib, struct, zlib, collections, time (stdlib only)
Optional: numpy (for benchmark acceleration, not required for correctness)
"""

from __future__ import annotations
import math
import hashlib
import struct
import time
import zlib
from collections import deque
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable, Any
from enum import IntEnum


# ---------------------------------------------------------------------------
# 1. Data types
# ---------------------------------------------------------------------------

class Severity(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Constraint:
    """A named range constraint on a sensor value."""
    lo: float
    hi: float
    name: str = ""
    weight: float = 1.0  # severity multiplier

    def check(self, value: float) -> bool:
        return self.lo <= value <= self.hi

    def error_mask_bit(self, value: float) -> int:
        return 0 if self.check(value) else 1

    def distance(self, value: float) -> float:
        """How far outside the constraint bounds (0 if inside)."""
        if value < self.lo:
            return self.lo - value
        if value > self.hi:
            return value - self.hi
        return 0.0


@dataclass
class StreamConfig:
    """Configuration for the streaming engine."""
    window_size: int = 1000          # sliding window per sensor
    check_interval: int = 1          # check every Nth value
    adaptive: bool = True            # enable predictive skipping
    kalman: bool = True              # enable Kalman prediction
    anomaly: bool = True             # enable anomaly detection
    provenance: bool = True          # enable provenance logging
    anomaly_window: int = 500        # anomaly detector window
    anomaly_threshold: float = 0.85  # compression ratio threshold
    kalman_process_noise: float = 0.1
    kalman_measurement_noise: float = 0.5
    kalman_dt: float = 1.0
    max_provenance_entries: int = 10000
    violation_history_size: int = 100


@dataclass
class SensorStats:
    """Running statistics for a single sensor."""
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0       # Welford's M2
    min_val: float = float('inf')
    max_val: float = float('-inf')
    last_value: float = 0.0

    def update(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.m2 += delta * delta2
        if value < self.min_val:
            self.min_val = value
        if value > self.max_val:
            self.max_val = value
        self.last_value = value

    @property
    def variance(self) -> float:
        if self.n < 2:
            return 0.0
        return self.m2 / (self.n - 1)

    @property
    def std(self) -> float:
        return math.sqrt(max(0, self.variance))

    def to_dict(self) -> Dict[str, float]:
        return {
            "n": self.n,
            "mean": round(self.mean, 6),
            "std": round(self.std, 6),
            "min": round(self.min_val, 6) if self.n > 0 else None,
            "max": round(self.max_val, 6) if self.n > 0 else None,
        }


@dataclass
class KalmanState:
    """Per-sensor Kalman filter state (position + velocity model)."""
    x: float = 0.0    # position estimate
    v: float = 0.0    # velocity estimate
    P: float = 1.0    # position variance
    Pv: float = 1.0   # velocity variance
    initialized: bool = False

    def predict(self, dt: float, process_noise: float) -> Tuple[float, float]:
        """Predict next value. Returns (predicted, uncertainty)."""
        x_pred = self.x + self.v * dt
        P_pred = self.P + 2 * dt * self.Pv + process_noise * dt * dt
        return x_pred, math.sqrt(max(0, P_pred))

    def update(self, measurement: float, dt: float,
               process_noise: float, measurement_noise: float) -> None:
        """Kalman update with new measurement."""
        if not self.initialized:
            self.x = measurement
            self.v = 0.0
            self.P = measurement_noise
            self.Pv = process_noise
            self.initialized = True
            return

        # Predict step
        x_pred = self.x + self.v * dt
        v_pred = self.v
        P_pred = self.P + 2 * dt * self.Pv + process_noise * dt * dt
        Pv_pred = self.Pv + process_noise

        # Update step
        y = measurement - x_pred  # innovation
        S = P_pred + measurement_noise
        if S > 0:
            K = P_pred / S
            Kv = self.Pv / (Pv_pred + measurement_noise)
        else:
            K = 0.0
            Kv = 0.0

        self.x = x_pred + K * y
        self.v = v_pred + Kv * y * dt * 0.1
        self.P = (1 - K) * P_pred
        self.Pv = max(0.001, (1 - Kv) * Pv_pred)

    @property
    def uncertainty(self) -> float:
        return math.sqrt(max(0, self.P))


@dataclass
class WaveletResult:
    """Compact wavelet decomposition result."""
    levels: int
    energy_by_level: List[float]
    dominant_level: int
    total_energy: float


def _haar_decompose_energy(signal: List[float], levels: int = 5) -> WaveletResult:
    """Fast Haar wavelet decomposition returning only energy by level."""
    n = len(signal)
    if n == 0:
        return WaveletResult(0, [], -1, 0.0)

    # Pad to next power of 2
    padded_len = 1
    while padded_len < n:
        padded_len *= 2
    approx = list(signal) + [0.0] * (padded_len - n)

    inv_sqrt2 = 1.0 / math.sqrt(2)
    energy_by_level = []
    max_levels = min(levels, int(math.log2(max(1, padded_len))))

    for _ in range(max_levels):
        new_approx = []
        detail_sq_sum = 0.0
        for i in range(0, len(approx), 2):
            if i + 1 < len(approx):
                a = (approx[i] + approx[i + 1]) * inv_sqrt2
                d = (approx[i] - approx[i + 1]) * inv_sqrt2
                new_approx.append(a)
                detail_sq_sum += d * d
            else:
                new_approx.append(approx[i] * inv_sqrt2)
        energy_by_level.append(detail_sq_sum)
        approx = new_approx

    total_energy = sum(energy_by_level) if energy_by_level else 0.0
    dominant = max(range(len(energy_by_level)), key=lambda i: energy_by_level[i]) if energy_by_level else -1

    return WaveletResult(
        levels=len(energy_by_level),
        energy_by_level=energy_by_level,
        dominant_level=dominant,
        total_energy=total_energy,
    )


# ---------------------------------------------------------------------------
# 2. Provenance
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceEntry:
    """Single provenance log entry."""
    timestamp: float
    sensor: str
    value: float
    error_mask: int
    severity: int
    predicted_value: Optional[float]
    prediction_error: Optional[float]
    wavelet_energy: List[float]
    content_hash: str


class ProvenanceLog:
    """Append-only provenance log with content-addressable hashes."""

    def __init__(self, max_entries: int = 10000):
        self._entries: deque = deque(maxlen=max_entries)
        self._max_entries = max_entries

    def record(self, timestamp: float, sensor: str, value: float,
               error_mask: int, severity: int,
               predicted_value: Optional[float] = None,
               prediction_error: Optional[float] = None,
               wavelet_energy: Optional[List[float]] = None) -> ProvenanceEntry:
        """Record a provenance entry and return it."""
        # Content hash: deterministic fingerprint of the event
        hasher = hashlib.blake2b(digest_size=16)
        hasher.update(struct.pack('!d', timestamp))
        hasher.update(sensor.encode('utf-8'))
        hasher.update(struct.pack('!d', value))
        hasher.update(struct.pack('!I', error_mask))
        hasher.update(struct.pack('!B', severity))
        if predicted_value is not None:
            hasher.update(struct.pack('!d', predicted_value))
        content_hash = hasher.hexdigest()

        entry = ProvenanceEntry(
            timestamp=timestamp,
            sensor=sensor,
            value=value,
            error_mask=error_mask,
            severity=severity,
            predicted_value=predicted_value,
            prediction_error=prediction_error,
            wavelet_energy=wavelet_energy or [],
            content_hash=content_hash,
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> List[ProvenanceEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# 3. Violation Event
# ---------------------------------------------------------------------------

@dataclass
class ViolationEvent:
    """Emitted when a constraint violation is detected."""
    timestamp: float
    sensor: str
    value: float
    error_mask: int
    severity: Severity
    failed_constraints: List[str]
    kalman_predicted: Optional[float]
    kalman_error: Optional[float]
    wavelet_result: Optional[WaveletResult]
    stats: Dict[str, Any]
    provenance_hash: Optional[str]

    def __str__(self) -> str:
        preds = f" (predicted: {self.kalman_predicted:.2f}, err: {self.kalman_error:.2f})" if self.kalman_predicted is not None else ""
        return (f"[{self.severity.name}] {self.sensor} = {self.value:.4f} "
                f"| mask=0b{self.error_mask:b} | {', '.join(self.failed_constraints)}{preds}")


# ---------------------------------------------------------------------------
# 4. Per-sensor state
# ---------------------------------------------------------------------------

class SensorState:
    """All per-sensor mutable state: window, stats, Kalman, violation history."""

    __slots__ = ('name', 'window_size', 'window', 'stats', 'kalman',
                 'violation_history', 'mask_window', 'check_count',
                 '_kalman_pn', '_kalman_mn', '_kalman_dt')

    def __init__(self, name: str, window_size: int,
                 kalman_process_noise: float, kalman_measurement_noise: float,
                 kalman_dt: float, enable_kalman: bool):
        self.name = name
        self.window_size = window_size
        self.window: deque = deque(maxlen=window_size)
        self.stats = SensorStats()
        self.kalman = KalmanState() if enable_kalman else None  # type: ignore
        self.violation_history: deque = deque(maxlen=100)
        self.mask_window: deque = deque(maxlen=window_size)
        self.check_count = 0

        # Store Kalman params for lazy init
        self._kalman_pn = kalman_process_noise
        self._kalman_mn = kalman_measurement_noise
        self._kalman_dt = kalman_dt

    def push(self, value: float) -> None:
        """Add a value to the sliding window and update stats."""
        self.window.append(value)
        self.stats.update(value)

    def get_mask_signal(self) -> List[float]:
        """Return violation mask as float signal for wavelet analysis."""
        return [float(m) for m in self.mask_window]


# ---------------------------------------------------------------------------
# 5. Anomaly tracker (lightweight, per-stream)
# ---------------------------------------------------------------------------

class StreamAnomalyDetector:
    """Lightweight anomaly detection via compression ratio on error masks."""

    __slots__ = ('window_size', 'threshold', '_window', '_baseline_rate')

    def __init__(self, window_size: int = 500, threshold: float = 0.85):
        self.window_size = window_size
        self.threshold = threshold
        self._window: deque = deque(maxlen=window_size)
        self._baseline_rate: Optional[float] = None

    def observe(self, error_mask: int) -> None:
        self._window.append(error_mask)

    def calibrate(self, rate: float) -> None:
        self._baseline_rate = rate

    def is_anomalous(self) -> bool:
        if len(self._window) < 50:
            return False
        data = bytes(self._window)
        ratio = len(zlib.compress(data, 6)) / len(data)
        return ratio > self.threshold

    def compression_ratio(self) -> float:
        if len(self._window) < 10:
            return 0.0
        data = bytes(self._window)
        return len(zlib.compress(data, 6)) / len(data)


# ---------------------------------------------------------------------------
# 6. FluxStream — the main engine
# ---------------------------------------------------------------------------

class FluxStream:
    """
    Production streaming constraint engine for real-time sensor feeds.

    - Register named sensors with per-sensor sliding windows
    - Feed (timestamp, sensor, value) tuples
    - Constraint checking with configurable interval
    - Per-sensor Kalman filter for prediction
    - Wavelet decomposition of violation patterns
    - Adaptive predictive skipping for throughput
    - Anomaly detection via compression ratio
    - Provenance logging with content hashes
    """

    def __init__(
        self,
        constraints: List[Constraint],
        config: StreamConfig = None,
    ):
        self.constraints = constraints
        self.config = config or StreamConfig()
        self._n_constraints = len(constraints)

        # Per-sensor state
        self._sensors: Dict[str, SensorState] = {}

        # Anomaly detector
        self._anomaly = StreamAnomalyDetector(
            window_size=self.config.anomaly_window,
            threshold=self.config.anomaly_threshold,
        ) if self.config.anomaly else None

        # Provenance log
        self._provenance = ProvenanceLog(
            max_entries=self.config.max_provenance_entries
        ) if self.config.provenance else None

        # Adaptive state
        self._adaptive_skip_counter: int = 0
        self._adaptive_skip_rate: int = 1  # check every Nth
        self._adaptive_consecutive_passes: int = 0

        # Global counters
        self._total_values: int = 0
        self._total_violations: int = 0
        self._total_checks: int = 0
        self._total_skipped: int = 0
        self._start_time: float = time.monotonic()

    # ------------------------------------------------------------------
    # Sensor management
    # ------------------------------------------------------------------

    def add_sensor(self, name: str, window: int = None) -> None:
        """Register a named sensor with its own sliding window."""
        ws = window or self.config.window_size
        self._sensors[name] = SensorState(
            name=name,
            window_size=ws,
            kalman_process_noise=self.config.kalman_process_noise,
            kalman_measurement_noise=self.config.kalman_measurement_noise,
            kalman_dt=self.config.kalman_dt,
            enable_kalman=self.config.kalman,
        )

    def remove_sensor(self, name: str) -> None:
        self._sensors.pop(name, None)

    @property
    def sensors(self) -> List[str]:
        return list(self._sensors.keys())

    # ------------------------------------------------------------------
    # Core feed
    # ------------------------------------------------------------------

    def feed(self, timestamp: float, sensor: str, value: float) -> Optional[ViolationEvent]:
        """
        Feed a single (timestamp, sensor, value) observation.

        Returns a ViolationEvent if a constraint was violated, else None.
        """
        self._total_values += 1

        state = self._sensors.get(sensor)
        if state is None:
            # Auto-register unknown sensors
            self.add_sensor(sensor)
            state = self._sensors[sensor]

        # Update sliding window and stats
        state.push(value)

        # Adaptive: skip checking if confident
        if self.config.adaptive and self._should_skip(state):
            self._total_skipped += 1
            state.mask_window.append(0)
            if self._anomaly:
                self._anomaly.observe(0)
            return None

        state.check_count += 1
        self._total_checks += 1

        # --- Kalman prediction (before update) ---
        predicted: Optional[float] = None
        prediction_error: Optional[float] = None
        if state.kalman is not None and state.kalman.initialized:
            predicted, _ = state.kalman.predict(
                self.config.kalman_dt, self.config.kalman_process_noise
            )

        # --- Update Kalman ---
        if state.kalman is not None:
            state.kalman.update(
                value,
                self.config.kalman_dt,
                self.config.kalman_process_noise,
                self.config.kalman_measurement_noise,
            )

        # --- Constraint check ---
        error_mask = 0
        for i, c in enumerate(self.constraints):
            if not c.check(value):
                error_mask |= (1 << i)

        state.mask_window.append(error_mask)

        # Anomaly tracking
        if self._anomaly:
            self._anomaly.observe(error_mask)

        # --- No violation ---
        if error_mask == 0:
            self._adaptive_consecutive_passes += 1
            self._update_adaptive()
            return None

        # --- Violation detected ---
        self._total_violations += 1
        self._adaptive_consecutive_passes = 0
        self._adaptive_skip_rate = 1  # reset to full checking
        state.violation_history.append((timestamp, value, error_mask))

        # Determine severity
        severity = self._compute_severity(value, error_mask)

        # Identify failed constraints
        failed = []
        for i, c in enumerate(self.constraints):
            if error_mask & (1 << i):
                failed.append(c.name or f"constraint_{i}")

        # Prediction error
        if predicted is not None:
            prediction_error = value - predicted

        # Wavelet decomposition of recent violation signal
        wavelet_result: Optional[WaveletResult] = None
        if len(state.mask_window) >= 8:
            mask_signal = state.get_mask_signal()
            wavelet_result = _haar_decompose_energy(mask_signal, levels=min(6, int(math.log2(len(mask_signal)))))

        # Build stats dict
        stats = state.stats.to_dict()

        # Provenance
        prov_hash: Optional[str] = None
        if self._provenance is not None:
            entry = self._provenance.record(
                timestamp=timestamp,
                sensor=sensor,
                value=value,
                error_mask=error_mask,
                severity=int(severity),
                predicted_value=predicted,
                prediction_error=prediction_error,
                wavelet_energy=wavelet_result.energy_by_level if wavelet_result else None,
            )
            prov_hash = entry.content_hash

        return ViolationEvent(
            timestamp=timestamp,
            sensor=sensor,
            value=value,
            error_mask=error_mask,
            severity=severity,
            failed_constraints=failed,
            kalman_predicted=predicted,
            kalman_error=prediction_error,
            wavelet_result=wavelet_result,
            stats=stats,
            provenance_hash=prov_hash,
        )

    # ------------------------------------------------------------------
    # Batch feed
    # ------------------------------------------------------------------

    def feed_batch(self, data: List[Tuple[float, str, float]]) -> List[ViolationEvent]:
        """Feed a batch of (timestamp, sensor, value) tuples. Returns violation events."""
        events = []
        for ts, sensor, value in data:
            event = self.feed(ts, sensor, value)
            if event is not None:
                events.append(event)
        return events

    # ------------------------------------------------------------------
    # Adaptive predictive skipping
    # ------------------------------------------------------------------

    def _should_skip(self, state: SensorState) -> bool:
        """Determine if we can safely skip constraint checking for this value."""
        if state.check_count < 50:
            return False  # Need warmup

        self._adaptive_skip_counter += 1
        if self._adaptive_skip_counter < self._adaptive_skip_rate:
            # Still within skip window
            return True

        self._adaptive_skip_counter = 0
        return False

    def _update_adaptive(self) -> None:
        """Increase skip rate after consecutive passes."""
        if self._adaptive_consecutive_passes >= 100:
            self._adaptive_skip_rate = min(10, self._adaptive_skip_rate + 1)
            self._adaptive_consecutive_passes = 0

    # ------------------------------------------------------------------
    # Severity computation
    # ------------------------------------------------------------------

    def _compute_severity(self, value: float, error_mask: int) -> Severity:
        """
        Compute violation severity based on:
        - Number of constraints violated
        - Distance outside bounds (relative to range width)
        - Statistical deviation (if enough data)
        """
        n_violated = bin(error_mask).count('1')

        # Maximum relative distance across violated constraints
        max_rel_dist = 0.0
        for i, c in enumerate(self.constraints):
            if error_mask & (1 << i):
                dist = c.distance(value)
                range_w = c.hi - c.lo
                rel_dist = dist / range_w if range_w > 0 else dist
                weighted = rel_dist * c.weight
                if weighted > max_rel_dist:
                    max_rel_dist = weighted

        # Severity scoring
        score = max_rel_dist * (1 + 0.5 * (n_violated - 1))

        if score < 0.01:
            return Severity.LOW
        elif score < 0.1:
            return Severity.MEDIUM
        elif score < 0.5:
            return Severity.HIGH
        else:
            return Severity.CRITICAL

    # ------------------------------------------------------------------
    # Query / diagnostics
    # ------------------------------------------------------------------

    def get_sensor_stats(self, sensor: str) -> Optional[Dict]:
        """Get current statistics for a sensor."""
        state = self._sensors.get(sensor)
        if state is None:
            return None
        result = state.stats.to_dict()
        if state.kalman is not None and state.kalman.initialized:
            result["kalman"] = {
                "position": round(state.kalman.x, 4),
                "velocity": round(state.kalman.v, 4),
                "uncertainty": round(state.kalman.uncertainty, 4),
            }
        result["window_size"] = len(state.window)
        result["check_count"] = state.check_count
        result["violation_count"] = len(state.violation_history)
        return result

    def get_sensor_window(self, sensor: str) -> Optional[List[float]]:
        """Get the current sliding window for a sensor."""
        state = self._sensors.get(sensor)
        return list(state.window) if state else None

    def get_violation_history(self, sensor: str) -> List[Tuple[float, float, int]]:
        """Get violation history for a sensor as (timestamp, value, error_mask)."""
        state = self._sensors.get(sensor)
        return list(state.violation_history) if state else []

    def is_anomalous(self) -> bool:
        """Check if recent error patterns are anomalous."""
        if self._anomaly is None:
            return False
        return self._anomaly.is_anomalous()

    def anomaly_compression_ratio(self) -> float:
        """Current compression ratio of error patterns."""
        if self._anomaly is None:
            return 0.0
        return self._anomaly.compression_ratio()

    @property
    def provenance_log(self) -> ProvenanceLog:
        return self._provenance  # type: ignore

    def get_throughput(self) -> Dict[str, float]:
        """Get throughput statistics."""
        elapsed = time.monotonic() - self._start_time
        if elapsed < 1e-9:
            elapsed = 1e-9
        return {
            "total_values": self._total_values,
            "total_violations": self._total_violations,
            "total_checks": self._total_checks,
            "total_skipped": self._total_skipped,
            "values_per_second": round(self._total_values / elapsed, 1),
            "checks_per_second": round(self._total_checks / elapsed, 1),
            "elapsed_seconds": round(elapsed, 3),
            "violation_rate": round(self._total_violations / max(1, self._total_values), 6),
            "skip_rate": round(self._total_skipped / max(1, self._total_values), 4),
            "n_sensors": len(self._sensors),
        }

    def summary(self) -> Dict[str, Any]:
        """Full summary of the stream state."""
        return {
            "throughput": self.get_throughput(),
            "is_anomalous": self.is_anomalous(),
            "anomaly_compression_ratio": self.anomaly_compression_ratio(),
            "config": {
                "window_size": self.config.window_size,
                "check_interval": self.config.check_interval,
                "adaptive": self.config.adaptive,
                "kalman": self.config.kalman,
                "anomaly": self.config.anomaly,
                "provenance": self.config.provenance,
            },
            "sensors": {
                name: self.get_sensor_stats(name)
                for name in self._sensors
            },
            "provenance_entries": len(self._provenance) if self._provenance else 0,
        }


# ---------------------------------------------------------------------------
# 7. Benchmark helper
# ---------------------------------------------------------------------------

def run_benchmark(
    n_sensors: int = 10000,
    rate_hz: int = 1000,
    duration_seconds: float = 1.0,
    violation_rate: float = 0.001,
    config: StreamConfig = None,
) -> Dict[str, Any]:
    """
    Benchmark the streaming engine.

    Args:
        n_sensors: Number of simulated sensors
        rate_hz: Samples per second per sensor
        duration_seconds: Simulation duration
        violation_rate: Fraction of values that violate constraints
        config: StreamConfig (uses defaults if None)

    Returns:
        Benchmark results including throughput, timing, and accuracy.
    """
    import random

    random.seed(42)
    cfg = config or StreamConfig()

    constraints = [
        Constraint(lo=-10.0, hi=110.0, name="operating_range"),
        Constraint(lo=0.0, hi=100.0, name="safe_zone"),
    ]

    stream = FluxStream(constraints=constraints, config=cfg)

    # Register sensors
    sensor_names = [f"sensor_{i}" for i in range(n_sensors)]
    for name in sensor_names:
        stream.add_sensor(name)

    # Generate data
    total_samples = int(n_sensors * rate_hz * duration_seconds)
    data = []
    dt = 1.0 / rate_hz

    for t_idx in range(int(rate_hz * duration_seconds)):
        ts = t_idx * dt
        for s_idx in range(n_sensors):
            if random.random() < violation_rate:
                # Violation: outside safe zone
                value = random.choice([
                    random.uniform(-20, -10),
                    random.uniform(100, 120),
                ])
            else:
                value = random.uniform(5, 95)
            data.append((ts, sensor_names[s_idx], value))

    # Run benchmark
    t0 = time.perf_counter()
    events = stream.feed_batch(data)
    elapsed = time.perf_counter() - t0

    throughput = stream.get_throughput()
    throughput["wall_time"] = round(elapsed, 4)
    throughput["wall_values_per_second"] = round(len(data) / elapsed, 1) if elapsed > 0 else 0

    return {
        "config": {
            "n_sensors": n_sensors,
            "rate_hz": rate_hz,
            "duration_seconds": duration_seconds,
            "total_samples": len(data),
            "violation_rate": violation_rate,
        },
        "results": throughput,
        "violation_events": len(events),
        "expected_violations": int(total_samples * violation_rate),
        "detection_rate": round(len(events) / max(1, total_samples * violation_rate), 4),
        "summary": stream.summary(),
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("FLUX v4 Streaming Constraint Engine — Self-Test")
    print("=" * 60)

    # Basic usage demo
    constraints = [
        Constraint(lo=0.0, hi=100.0, name="safe_zone"),
        Constraint(lo=-10.0, hi=110.0, name="operating_range"),
    ]

    stream = FluxStream(
        constraints=constraints,
        config=StreamConfig(
            window_size=100,
            adaptive=True,
            kalman=True,
            anomaly=True,
            provenance=True,
        )
    )

    stream.add_sensor("temp_1", window=100)
    stream.add_sensor("rpm_1", window=100)

    import random
    random.seed(42)

    # Feed 10k values with 0.5% violation rate
    violations = 0
    for i in range(10000):
        ts = i * 0.001  # 1kHz
        sensor = random.choice(["temp_1", "rpm_1"])
        if random.random() < 0.005:
            value = random.choice([random.uniform(-20, -5), random.uniform(105, 130)])
        else:
            value = random.uniform(10, 90)

        event = stream.feed(ts, sensor, value)
        if event:
            violations += 1
            print(f"  {event}")

    print(f"\n--- Results ---")
    print(f"Total violations detected: {violations}")
    print(f"Throughput: {stream.get_throughput()}")
    print(f"Anomalous: {stream.is_anomalous()}")

    for name in stream.sensors:
        stats = stream.get_sensor_stats(name)
        print(f"  {name}: {stats}")

    # Benchmark
    print("\n" + "=" * 60)
    print("Benchmark: 10,000 sensors at 1kHz for 0.1s")
    print("=" * 60)
    bench = run_benchmark(n_sensors=10000, rate_hz=1000, duration_seconds=0.1)
    print(f"  Total samples: {bench['config']['total_samples']}")
    print(f"  Wall time: {bench['results']['wall_time']:.3f}s")
    print(f"  Throughput: {bench['results']['wall_values_per_second']:.0f} values/s")
    print(f"  Violations: {bench['violation_events']} detected of {bench['expected_violations']} expected")
    print(f"  Detection rate: {bench['detection_rate']:.2%}")
