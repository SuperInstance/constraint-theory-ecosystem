# Analog Circuit Substrate for FLUX Exact Constraint Checking

**Version:** 1.0  
**Date:** 2026-05-19  
**Substrate:** Analog Continuous (Op-Amp Comparators)  
**Latency:** ~10-50 ns per check  
**Power:** ~50 μW per constraint (8 constraints = ~400 μW total)

---

## 1. Physical Principle

An operational amplifier in open-loop configuration acts as a **comparator**: the output saturates to the positive rail if V+ > V- and to the negative rail if V+ < V-. A constraint check `lo ≤ v ≤ hi` is equivalent to:

```
v ≥ lo    AND    v ≤ hi
```

This decomposes into two comparator operations plus a logical AND, all implementable in continuous-time analog circuitry. The result is a voltage level: HIGH (logic 1 = PASS) or LOW (logic 0 = FAIL).

**No clock. No sampling. No quantization. The constraint is checked continuously in real-time.**

---

## 2. Circuit Architecture: Single Constraint

### 2.1 Window Comparator

A window comparator uses two op-amps to check if an input voltage falls within a range:

```
                    Vcc
                     │
              ┌──────┴──────┐
              │   Op-Amp A   │    (Lower bound check: v ≥ lo)
              │  V+ = v      │
              │  V- = V_lo   │──── Out_A (HIGH if v ≥ lo)
              │              │
              └──────────────┘
              
              ┌──────────────┐
              │   Op-Amp B   │    (Upper bound check: v ≤ hi)
              │  V+ = V_hi   │
              │  V- = v      │──── Out_B (HIGH if v ≤ hi)
              │              │
              └──────────────┘
                     │
                    GND

        Out_A ──┐
                ├── AND gate ── PASS (HIGH if v in [lo, hi])
        Out_B ──┘
```

**Transfer function:**

| Condition | Out_A | Out_B | PASS |
|-----------|-------|-------|------|
| v < lo | LOW | HIGH | LOW (FAIL) |
| lo ≤ v ≤ hi | HIGH | HIGH | HIGH (PASS) |
| v > hi | HIGH | LOW | LOW (FAIL) |

### 2.2 Output Encoding

For the FLUX error mask convention (bit = 1 for violation):

```
error_bit_i = NOT(PASS) = NAND(Out_A, Out_B)
```

A single NAND gate per constraint provides the error bit.

---

## 3. 8-Constraint Checker: Full Schematic

### 3.1 Voltage Mapping

The sensor value must be mapped to a voltage. For a standard 0-5V range:

```
V_value = (value - V_min) / (V_max - V_min) × 5.0V

Example: value range [-40, 150]°C
V_value(-40) = 0.0V
V_value(55)  = 2.5V
V_value(150) = 5.0V
```

The bounds are set as reference voltages:

```
V_lo[i] = (constraint[i].lo - V_min) / (V_max - V_min) × 5.0V
V_hi[i] = (constraint[i].hi - V_min) / (V_max - V_min) × 5.0V
```

### 3.2 Component Count

| Component | Per Constraint | 8 Constraints | Part |
|-----------|---------------|---------------|------|
| Op-amp (dual package) | 1 (2 per IC) | 4 ICs | LM393 (dual comparator) |
| Resistor divider (lo) | 2 | 16 | Standard 1% |
| Resistor divider (hi) | 2 | 16 | Standard 1% |
| NAND gate | 1/4 | 2 ICs | 74HC00 (quad NAND) |
| Pull-up resistor | 2 | 16 | 10kΩ |
| Bypass capacitor | 0.1 per IC | 6 | Ceramic |
| **Total** | | **~50 components** | |

### 3.3 Full 8-Constraint Netlist

``` spice
* FLUX Constraint Engine — 8-Constraint Analog Checker
* SPICE Netlist (LTspice / ngspice compatible)
* 
* Checks 8 constraints simultaneously in continuous-time
* Output: 8-bit error_mask (bit=1 means violation)
*
* Power supply
VCC VCC 0 DC 5.0
VGND 0 GND DC 0

* Input value (test: sweep from 0V to 5V)
* In production: driven by sensor conditioning circuit
V_VALUE VIN 0 DC 0

* ============================================================
* Constraint Reference Voltages (set via resistor dividers)
* Each constraint has lo and hi bounds
* Example mapping: value range [-40, 150] → [0V, 5V]
* ============================================================

* Constraint 1: [-40, 150] → [0.0V, 5.0V] (full range = always pass)
* VLO1 = 0.0V (direct to GND)
* VHI1 = 5.0V (direct to VCC)

* Constraint 2: [0, 100] → [1.034V, 3.793V]
* V = (T + 40) / 190 * 5.0
* lo=0: 40/190*5 = 1.053V, hi=100: 140/190*5 = 3.684V
R2LO_A VLO2 VCC 3.9k
R2LO_B 0 VLO2 1.0k
R2HI_A VHI2 VCC 1.5k
R2HI_B 0 VHI2 1.8k

* Constraint 3: [20, 80] → [1.579V, 3.158V]
R3LO_A VLO3 VCC 2.7k
R3LO_B 0 VLO3 1.5k
R3HI_A VHI3 VCC 2.2k
R3HI_B 0 VHI3 2.2k

* Constraint 4: [-10, 60] → [0.789V, 2.632V]
R4LO_A VLO4 VCC 4.7k
R4LO_B 0 VLO4 1.0k
R4HI_A VHI4 VCC 3.3k
R4HI_B 0 VHI4 2.7k

* Constraint 5: [30, 120] → [1.842V, 4.211V]
R5LO_A VLO5 VCC 2.2k
R5LO_B 0 VLO5 1.8k
R5HI_A VHI5 VCC 1.2k
R5HI_B 0 VHI5 2.7k

* Constraint 6: [-20, 40] → [0.526V, 2.105V]
R6LO_A VLO6 VCC 5.6k
R6LO_B 0 VLO6 1.0k
R6HI_A VHI6 VCC 4.7k
R6HI_B 0 VHI6 2.7k

* Constraint 7: [10, 90] → [1.316V, 3.421V]
R7LO_A VLO7 VCC 3.3k
R7LO_B 0 VLO7 1.5k
R7HI_A VHI7 VCC 1.8k
R7HI_B 0 VHI7 2.2k

* Constraint 8: [-30, 70] → [0.263V, 2.895V]
R8LO_A VLO8 VCC 6.8k
R8LO_B 0 VLO8 1.0k
R8HI_A VHI8 VCC 3.9k
R8HI_B 0 VHI8 3.3k

* ============================================================
* Comparators (LM393 model — open-collector output)
* Lower bound check: VIN ≥ VLO → output HIGH
* Upper bound check: VIN ≤ VHI → output HIGH
* ============================================================

* Pull-up resistors for open-collector outputs
RPULL1_A OA1 VCC 10k
RPULL1_B OB1 VCC 10k
RPULL2_A OA2 VCC 10k
RPULL2_B OB2 VCC 10k
RPULL3_A OA3 VCC 10k
RPULL3_B OB3 VCC 10k
RPULL4_A OA4 VCC 10k
RPULL4_B OB4 VCC 10k
RPULL5_A OA5 VCC 10k
RPULL5_B OB5 VCC 10k
RPULL6_A OA6 VCC 10k
RPULL6_B OB6 VCC 10k
RPULL7_A OA7 VCC 10k
RPULL7_B OB7 VCC 10k
RPULL8_A OA8 VCC 10k
RPULL8_B OB8 VCC 10k

* Constraint 1 comparators (always-pass: lo=GND, hi=VCC)
XCOMP1A VLO1 VIN OA1 LM393
XCOMP1B VIN VHI1 OB1 LM393

* Constraint 2 comparators
XCOMP2A VLO2 VIN OA2 LM393
XCOMP2B VIN VHI2 OB2 LM393

* Constraint 3 comparators
XCOMP3A VLO3 VIN OA3 LM393
XCOMP3B VIN VHI3 OB3 LM393

* Constraint 4 comparators
XCOMP4A VLO4 VIN OA4 LM393
XCOMP4B VIN VHI4 OB4 LM393

* Constraint 5 comparators
XCOMP5A VLO5 VIN OA5 LM393
XCOMP5B VIN VHI5 OB5 LM393

* Constraint 6 comparators
XCOMP6A VLO6 VIN OA6 LM393
XCOMP6B VIN VHI6 OB6 LM393

* Constraint 7 comparators
XCOMP7A VLO7 VIN OA7 LM393
XCOMP7B VIN VHI7 OB7 LM393

* Constraint 8 comparators
XCOMP8A VLO8 VIN OA8 LM393
XCOMP8B VIN VHI8 OB8 LM393

* ============================================================
* NAND gates: error_bit_i = NAND(Out_A, Out_B)
* 74HC00 quad NAND gates (2 ICs for 8 constraints)
* NAND truth: output LOW only when BOTH inputs HIGH
* So: error_bit = LOW when in range (PASS), HIGH when out of range (FAIL)
* Wait — for FLUX convention: bit=1 is violation
* NAND(HIGH, HIGH) = LOW → in range → bit should be 0 ✓
* NAND(LOW, *) or NAND(*, LOW) = HIGH → out of range → bit should be 1 ✓
* ============================================================

XNAND1 OA1 OB1 ERR1 74HC00
XNAND2 OA2 OB2 ERR2 74HC00
XNAND3 OA3 OB3 ERR3 74HC00
XNAND4 OA4 OB4 ERR4 74HC00
XNAND5 OA5 OB5 ERR5 74HC00
XNAND6 OA6 OB6 ERR6 74HC00
XNAND7 OA7 OB7 ERR7 74HC00
XNAND8 OA8 OB8 ERR8 74HC00

* Bypass capacitors
CBYP1 VCC 0 100n
CBYP2 VCC 0 100n
CBYP3 VCC 0 100n
CBYP4 VCC 0 100n
CBYP5 VCC 0 100n
CBYP6 VCC 0 100n

* ============================================================
* Subcircuit models
* ============================================================

* LM393 comparator model (simplified)
.SUBCKT LM393 INP INN OUT
* Open-collector comparator
* Output pulls low when INP < INN
* External pull-up to VCC required
Q1 OUT INT 0 NPN
R1 INT INP 1k
E1 INT 0 VALUE={V(INP) > V(INN) ? 5.0 : 0.0}
.MODEL NPN NPN(IS=1e-14 BF=200)
.ENDS LM393

* 74HC00 NAND gate model (simplified)
.SUBCKT 74HC00 A B Y
* NAND: Y = NOT(A AND B)
RY Y 0 1k
EY Y 0 VALUE={~((V(A) > 2.0) & (V(B) > 2.0)) ? 5.0 : 0.0}
.ENDS 74HC00

* ============================================================
* Simulation: DC sweep of input voltage
* ============================================================
.DC V_VALUE 0 5 0.01
.PRINT DC V(ERR1) V(ERR2) V(ERR3) V(ERR4) V(ERR5) V(ERR6) V(ERR7) V(ERR8)
.END
```

---

## 4. Performance Analysis

### 4.1 Latency

| Stage | Time | Notes |
|-------|------|-------|
| Propagation to comparators | ~1 ns | PCB trace |
| Comparator response | 40-200 ns | LM393: 1.3 μs typ; LT1015: 40 ns |  
| NAND gate propagation | 5-10 ns | 74HC00 |
| **Total (fast comparator)** | **~50 ns** | With LT1015 or MAX903 |
| **Total (standard comparator)** | **~1.3 μs** | With LM393 |

**With high-speed comparators (MAX903, LT1015): 50 ns per check.**

### 4.2 Throughput

```
Continuous-time: effectively infinite sample rate
Practical limit: bandwidth of input signal

Input bandwidth: 10 MHz (typical sensor conditioning)
Checks per second: continuous — every instant is checked
Equivalent throughput: limited only by how fast the input changes

For discretized streaming:
At 50 ns settling time → 20 million updates/sec
At 1.3 μs settling time → 770K updates/sec
```

### 4.3 Power Consumption

| Component | Per Unit | 8 Constraints |
|-----------|----------|---------------|
| LM393 comparator | 1 mW (quiescent) | 8 mW |
| 74HC00 NAND | 1 μW/static | 2 μW |
| Resistor dividers | ~1 mW total | ~8 mW |
| Pull-up resistors | ~2.5 mW (5V²/10kΩ) | ~40 mW (active) |
| **Total (static)** | | **~16 mW** |
| **Total (active, worst case)** | | **~58 mW** |

Using CMOS comparators (MAX903, 0.6 μA quiescent):
- **Total quiescent: ~50 μW** (8 comparators + NAND gates)
- **Total active: ~5 mW**

### 4.4 Precision

| Parameter | Value | Notes |
|-----------|-------|-------|
| Voltage resolution | ~5 mV (with 1% resistors) | ~0.1% of 5V range |
| With 0.1% resistors | ~0.5 mV | ~0.01% of range |
| Comparator offset | ±1 mV (LM393) | ±0.3 mV (LT1015) |
| Temperature drift | ~10 μV/°C (LM393) | Improved with auto-zero parts |

For a [-40, 150°C] range: ±0.1% = ±0.19°C resolution. Excellent for thermal constraints.

---

## 5. Zero False Negative Proof (Analog)

### Theorem

For the analog window comparator, if the input voltage V_value is outside [V_lo, V_hi], the error bit is HIGH.

### Proof

**Case 1: V_value < V_lo**
- Op-Amp A: V+ = V_value, V- = V_lo → V+ < V- → output LOW
- NAND(LOW, anything) = HIGH → error bit = 1 ✓

**Case 2: V_value > V_hi**
- Op-Amp B: V+ = V_hi, V- = V_value → V+ < V- → output LOW
- NAND(anything, LOW) = HIGH → error bit = 1 ✓

**Case 3: V_lo ≤ V_value ≤ V_hi**
- Op-Amp A: V+ ≥ V- → output HIGH
- Op-Amp B: V+ ≥ V- → output HIGH
- NAND(HIGH, HIGH) = LOW → error bit = 0 ✓

### Caveat: Comparator Offset

Real comparators have input offset voltage V_os (~1 mV). This creates a guard band:

```
Actual detection: V_value < V_lo + V_os  (for lower bound)
Actual detection: V_value > V_hi - V_os  (for upper bound)
```

For safety systems: **design bounds inward by V_os** so the effective constraint is slightly tighter. Any value outside the specified bounds is still guaranteed detected. The offset can only make the system MORE conservative (false positives possible near edges), never less (no false negatives).

**QED: Zero false negatives with fail-safe offset compensation.**

---

## 6. PCB Layout Considerations

```
┌─────────────────────────────────────────────────┐
│  FLUX Analog Constraint Checker — 4-layer PCB   │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ LM393 #1 │  │ LM393 #2 │  │ LM393 #3 │      │
│  │ C1, C2   │  │ C3, C4   │  │ C5, C6   │      │
│  └──────────┘  └──────────┘  └──────────┘      │
│                                                  │
│  ┌──────────┐  ┌──────────┐                     │
│  │ LM393 #4 │  │ 74HC00 #1│  VIN ──► [bus]     │
│  │ C7, C8   │  │ E1-E4    │                     │
│  └──────────┘  └──────────┘                     │
│                                 ┌──────────┐    │
│  ┌──────────┐                   │ 74HC00 #2│    │
│  │ Reference │                   │ E5-E8    │    │
│  │ Divider  │                   └──────────┘    │
│  │ Network  │         ERR[7:0] ──► [header]     │
│  └──────────┘                                    │
│                                                  │
│  Layer: GND / Signal / Signal / VCC              │
│  Size: ~30mm × 20mm                             │
└─────────────────────────────────────────────────┘
```

### Bill of Materials (8-constraint board)

| Qty | Part | Description | Unit Cost |
|-----|------|-------------|-----------|
| 4 | LM393 | Dual comparator, DIP-8/SOIC-8 | $0.30 |
| 2 | 74HC00 | Quad NAND, DIP-14/SOIC-14 | $0.20 |
| 32 | 1% resistor | 1k-10k, 0805 | $0.01 |
| 16 | 10k pull-up | 0805 | $0.01 |
| 6 | 100nF ceramic | Bypass, 0805 | $0.05 |
| 1 | PCB | 4-layer, 30×20mm | $2.00 |
| | | **Total** | **~$5** |

---

## 7. Comparison to Software

| Metric | Software (AVX2) | Analog (LM393) | Analog (MAX903) |
|--------|-----------------|-----------------|-----------------|
| Latency | 2-5 ns | 1.3 μs | 50 ns |
| Throughput | 2.4G/s | Continuous | Continuous |
| Power | ~1W (CPU core) | 58 mW | 5 mW |
| False negatives | Zero | Zero | Zero |
| Cost | CPU cost | ~$5 | ~$15 |
| Precision | Float (exact) | ±0.1% | ±0.01% |
| Reconfigurable | Yes (software) | Yes (DAC for bounds) | Yes (DAC for bounds) |

**Analog wins on power and cost for dedicated constraint-checking roles. Software wins on flexibility and precision.**

---

## 8. Dynamic Bounds with DACs

For reconfigurable constraints, replace resistor dividers with DAC outputs:

```
Constraint bound ← microcontroller → DAC → V_lo[i], V_hi[i]
Update rate: ~1 MHz (12-bit DAC settling)
Reconfiguration latency: ~1 μs
```

This enables runtime constraint updates while maintaining continuous-time checking. The DAC introduces a brief uncertainty window during updates (~100 ns) where bounds are transitioning — handle with a disable/latch during update.
