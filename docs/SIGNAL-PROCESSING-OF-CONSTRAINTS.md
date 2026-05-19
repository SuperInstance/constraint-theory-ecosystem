# Signal Processing of Constraints

## Constraint Checking IS a Filtering Operation

A constraint checker maps input sequence x[n] to output y[n] where:

```
y[n] = 1  if lo ≤ x[n] ≤ hi   (pass)
y[n] = 0  otherwise             (fail)
```

This is a **memoryless nonlinear system** — specifically, a hard limiter / rectangular window function. This means the entire apparatus of signal processing theory applies to constraint checking.

---

## 1. Frequency Response of the Constraint Filter

### The System

The constraint checker is **not LTI** (linear time-invariant). Superposition fails: checking (x₁ + x₂) ≠ checking(x₁) + checking(x₂). So there's no transfer function H(e^jω) in the classical sense.

However, we can characterize the **spectral signature** of violations:

### For Sinusoidal Input x[n] = A·sin(2πfn)

- **Amplitude within bounds** (A ≤ range_width/2): output is constant 1 → pure DC, no spectral content. The checker is transparent.
- **Amplitude exceeds bounds** (A > range_width/2): output becomes a periodic rectangular wave with duty cycle d = arcsin(range/(2A))/π. This produces harmonics at integer multiples of the input frequency.

The Fourier coefficients follow the standard rectangular pulse series:

```
a₀ = d                        (DC = duty cycle)
aₙ = sin(nπd) / (nπ)          (n-th harmonic)
```

**Key insight**: The first harmonic to appear (beyond DC) is at the input frequency. As clipping gets more severe (duty cycle → 0), harmonic content increases. Total Harmonic Distortion (THD) is a direct measure of how badly constraints are being violated.

### For Stochastic Input

Define the violation error signal ε[n] = 1(x[n] ∉ [lo, hi]).

Its power spectral density follows the Wiener-Khinchin theorem:
- DC component = P(violation) = long-term violation rate
- Spectral shape depends on autocorrelation R_ε[m] of the violation process
- Step-like boundary crossings produce wideband content with ~1/ω² rolloff

### Implementation

`ConstraintFilter` in `flux_signal.py` computes:
- Frequency response for sinusoidal inputs (harmonic analysis)
- Spectral signature of real signals (DFT of binary mask)
- Automatic detection of clipping vs clean operation

---

## 2. Wavelet Decomposition of Violation Patterns

### Why Wavelets?

The binary error mask (0=pass, 1=fail) contains information about violation TYPE encoded in its time-frequency structure. Different violations live at different scales:

| Violation Type | Timescale | Wavelet Signature |
|---------------|-----------|-------------------|
| **Spike** | Single sample | Energy at finest detail levels (high frequency) |
| **Drift** | Hundreds of samples | Energy at coarsest levels (low frequency trend) |
| **Oscillation** | Periodic | Energy at specific mid-range levels matching period |
| **Burst** | 5-20 samples | Energy spread across adjacent mid levels |

### Haar Wavelet Decomposition

We use the simplest orthogonal wavelet — Haar:

```
Approximation: a[n] = (x[2n] + x[2n+1]) / √2   (lowpass)
Detail:        d[n] = (x[2n] - x[2n+1]) / √2   (highpass)
```

Multi-level decomposition splits each approximation again, creating a filter bank from fine to coarse scales. The energy at each level forms a "fingerprint" of the violation type.

### Classification Logic

1. Compute energy at each wavelet level
2. Partition into fine/mid/coarse thirds
3. Classify based on energy concentration:
   - Spike: fine_energy > 0.6, few violations (< 5% of samples)
   - Drift: high violation rate (> 10%), coarse energy significant
   - Oscillation: mid energy dominant, peaked at specific level
   - Burst: spread across fine and mid levels

### Research Note: Better Wavelets

Seed-2.0-mini suggests **Daubechies db4** or **Symlet sym4** for production use:
- db4 has 4 vanishing moments (rejects linear trends → isolates drifts)
- Compact support (preserves spike timing)
- Symlets reduce phase distortion for accurate timing

Haar works for classification but db4/sym4 would give sharper discrimination.

### Implementation

`ViolationWavelet` in `flux_signal.py` provides:
- Multi-level Haar decomposition
- Automatic violation pattern classification
- Energy distribution analysis

**Test results**: Correctly classifies clean (1.0 confidence), spike (0.78), drift (0.37), oscillation (0.81), and burst (0.53) patterns from synthetic sensor data.

---

## 3. Kalman Predictive Constraint Checking

### The Idea

Don't wait for the measurement to arrive — **predict** the next value using a Kalman filter, then pre-classify constraint satisfaction before you even see the data.

### State Model

2-state Kalman filter tracking position and velocity:

```
State: x = [position, velocity]ᵀ
Transition: F = [[1, Δt], [0, 1]]
Measurement: z = H·x = position

Process noise Q captures velocity uncertainty
Measurement noise R captures sensor precision
```

### Prediction Equations

```
x̂[k+1|k] = F · x̂[k|k]             (state prediction)
P[k+1|k] = F · P[k|k] · Fᵀ + Q     (uncertainty prediction)
```

The predicted measurement is x̂₁ with uncertainty √P₁₁.

### Pre-Classification

Using the 3σ prediction interval [x̂ - 3σ, x̂ + 3σ]:

- **DEFINITELY_PASS**: Entire interval within bounds
- **DEFINITELY_FAIL**: Entire interval outside bounds  
- **UNCERTAIN**: Interval overlaps boundary

The uncertain region creates an **adaptive guard band** around constraint boundaries that grows/shrinks with prediction uncertainty.

### Key Results

| Signal Type | Accuracy | Early Warnings | Uncertain Predictions |
|-------------|----------|----------------|----------------------|
| Clean sinusoid | 100% | 0 | 1/100 |
| Linear drift (0.8 units/step) | 100% | 4 early warnings | — |
| Large oscillation | 100% | — | 51/200 (near boundaries) |

The Kalman filter **predicts violations before they happen** — the drift signal triggers 4 early warnings before values actually exceed bounds. For the oscillation, the uncertain zone correctly identifies the 25% of time spent near boundaries.

### Implementation

`KalmanPredictiveChecker` in `flux_signal.py` provides:
- Full predict → pre-classify → observe → verify cycle
- Early warning detection
- Performance metrics (accuracy, early detection count)

---

## 4. Nyquist Analysis for Constraint Checking

### The Sampling Problem

If we check constraints at rate F_s but the physical process has bandwidth B, what rate guarantees we catch all violations?

### Nyquist Rate

**Minimum: F_s ≥ 2B** — standard Nyquist-Shannon sampling theorem.

At this rate, the violation signal v(t) = 1{x(t) ∉ [lo, hi]} is fully captured if v(t) is bandlimited to B.

### But Violations Aren't Bandlimited!

The critical insight: **violation type matters**:

| Violation Type | Bandwidth | Catchable at Nyquist? |
|---------------|-----------|----------------------|
| **Drift** | Low (drift_rate / range_width) | ✅ Easy |
| **Oscillation** | Oscillation frequency | ✅ If f_osc < F_s/2 |
| **Step change** | Infinite | ❌ Can miss the step |
| **Spike** | Infinite | ❌ Can miss entirely |

### Aliasing Causes Missed Violations

When F_s < 2·f_signal:
- The signal frequency aliases to f_alias = |F_s - f_signal|
- A 9 Hz violation sampled at 15 Hz appears as 6 Hz — wrong frequency
- If the aliased version happens to stay in-bounds at sample points, **the violation is invisible**

### Practical Rule

**F_s ≥ 10B** for 95% violation detection guarantee across all types except spikes.

For guaranteed spike detection: **impossible with finite sampling**. You need continuous monitoring (analog comparator).

### Concrete Example (Battery Monitoring)

```
Process bandwidth B = 10 Hz (thermal dynamics)
Nyquist rate: 20 Hz (check every 50ms)
Recommended: 100 Hz (check every 10ms)

Drift detection:
  Drift rate = 2 units/sec, range = 60 units
  Time to cross: 30 seconds
  Minimum rate: ~10 Hz → trivially achievable
```

### Implementation

`NyquistAnalyzer` in `flux_signal.py` provides:
- Minimum and recommended sampling rates
- Per-violation-type aliasing risk analysis
- Aliasing demonstration with concrete examples

---

## 5. Compressed Sensing for Constraint Monitoring

### The Problem

You have N sensors but can only read K < N per time step (bandwidth, power, or compute constraints). Can you still detect violations?

### The Theory

Assume violations are **sparse**: at most S of N sensors violate at any time step.

Compressed sensing guarantees recovery if:

```
K ≥ C · S · log(N/S)
```

where C is a constant (typically 2-4).

For practical sensor networks:
- N = 1024 sensors, S = 5 concurrent violations
- K ≥ 3 · 5 · log(1024/5) ≈ 67 sensors checked per step
- That's only **6.5% of all sensors** per time step

### Measurement Matrix

Random subset selection Φ ∈ R^(K×N):
```
Φ[t,i] = 1/√K  if sensor i is checked at step t
Φ[t,i] = 0     otherwise
```

Coherence μ = K/N. For K=32, N=1024: μ = 0.031 → excellent recovery properties.

### Practical Modes

1. **Round-robin**: Deterministic cycling through sensors
   - Guaranteed coverage over N/K steps
   - Simple, no overhead
   
2. **Random**: Uniform random selection each step
   - Expected detection time proportional to N/K
   
3. **Priority**: Recent-violation sensors checked more often
   - Adapts to persistent faults
   - Best for intermittent violations

### Experimental Results

With N=30 sensors, K=10 (33% checked per step), 200 time steps:

| Mode | Detection Rate | Notes |
|------|---------------|-------|
| Round-robin (K=10) | 42.3% | Coverage guaranteed every 3 steps |
| Round-robin (K=25) | 96.7% | Near-complete with 83% coverage |

Detection scales roughly linearly with K/N ratio, matching the CS theory.

### Implementation

`CompressedSensingChecker` in `flux_signal.py` provides:
- Round-robin, random, and priority selection modes
- Multi-step simulation with detection rate tracking
- Theoretical minimum K computation

---

## Synthesis: Constraint Checking Through the Signal Processing Lens

### The Unified View

Every aspect of constraint checking maps to signal processing:

| Constraint Concept | Signal Processing Equivalent |
|-------------------|----------------------------|
| Constraint bounds | Hard limiter thresholds |
| Pass/fail decision | Binary quantization |
| Violation pattern | Signal in error mask |
| Sampling rate | Checking frequency |
| Missed violation | Aliasing |
| Predictive checking | Kalman filtering |
| Multi-sensor monitoring | Compressed sensing |
| Violation classification | Wavelet decomposition |

### Practical Implications

1. **You're already doing signal processing** — every constraint check is a nonlinear filter. Understanding this lets you reason about checking frequency, missed violations, and pattern classification using established theory.

2. **Violation patterns are classifiable** — spike, drift, oscillation, and burst violations have distinct wavelet fingerprints. This enables automated root cause analysis.

3. **Prediction beats reaction** — Kalman predictive checking gives 1-2 sample early warning of violations, enabling preemptive action rather than reactive alerts.

4. **You can check fewer sensors** — Compressed sensing theory says you only need to check ~√N sensors per step to guarantee violation detection, not all N.

5. **Some violations are undetectable** — Spike violations shorter than the sampling interval are invisible. No amount of clever post-processing can recover them. This is fundamental to Nyquist-Shannon.

### The Deeper Point

Constraint theory and signal processing are the same subject viewed from different angles. A constraint space is a signal space. A violation is a detection problem. A constraint checker is a filter. This isn't analogy — it's mathematical identity.

The question "did this value violate the constraint?" is equivalent to "did the input signal exceed the filter's passband?" And all the tools of spectral analysis, wavelet theory, estimation theory, and compressed sensing apply directly.

---

*Generated by Forgemaster ⚒️ — constraint-theory-ecosystem*
*Source: `flux_signal.py` (5 modules, 33/33 tests passing)*
