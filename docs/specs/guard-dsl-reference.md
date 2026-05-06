# GUARD DSL Language Reference

**Version:** 1.0
**Target:** Constraint Theory Ecosystem
**Compilation Target:** FLUX-C Bytecode

## Overview

The GUARD DSL (Constraint Specification Language) is a domain-specific language for expressing safety-critical constraints in embedded systems. Like GD&T (Geometric Dimensioning & Tolerancing) provides precision specifications for mechanical parts, GUARD DSL provides precise constraint specifications for software behavior.

GUARD constraints compile to FLUX-C bytecode for deterministic execution on resource-constrained hardware (ARM Cortex-R5, 180MHz, 512KB RAM, 2MB Flash).

## Language Philosophy

**Constraint-First Design:** Constraints are not afterthoughts but primary design artifacts that define system behavior boundaries.

**Physical Metaphor:** Every software constraint corresponds to a physical constraint (pressure limits, temperature bounds, timing deadlines).

**Formal Verification:** GUARD expressions are mathematically verifiable and compile to provably safe bytecode.

## 1. BASIC CONSTRAINTS

### 1.1 Range Constraints

```guard
GUARD sensor_temp IN [0, 85]
  SEVERITY CRITICAL
  STANDARD 'DO-178C DAL A'
  UNIT 'degrees_C'
  SCALE 100
```

**Semantics:** Asserts that `sensor_temp` value falls within inclusive bounds [0, 85].

**Physical Analogy:** Temperature sensor operating range specification (0°C to 85°C).

**Compiled Bytecode:**
```flux-c
CONST_LOAD 0x00     ; Load lower bound (0)
CONST_LOAD 0x55     ; Load upper bound (85)
RANGE_CHECK 0x01    ; Check bounds for variable ID 0x01
GUARD_TRAP 0xFF     ; Trap on violation with CRITICAL severity
```

### 1.2 Equality Constraints

```guard
GUARD boot_sequence EQUAL 0xDEADBEEF
  SEVERITY CRITICAL
  STANDARD 'DO-178C DAL A'
```

**Semantics:** Asserts exact equality with specified value.

**Physical Analogy:** Security key validation - must match exactly.

**Compiled Bytecode:**
```flux-c
CONST_LOAD 0xDEAD   ; Load expected value high word
CONST_LOAD 0xBEEF   ; Load expected value low word
EQ                  ; Compare for equality
ASSERT              ; Assert true or trap
```

### 1.3 Exclusion Constraints

```guard
GUARD fault_code NOT_IN [0x8000, 0x8FFF]
  SEVERITY WARNING
  STANDARD 'MISRA-C 2012'
```

**Semantics:** Asserts value does NOT fall within specified range.

**Physical Analogy:** Forbidden frequency bands in radio systems.

**Compiled Bytecode:**
```flux-c
CONST_LOAD 0x8000   ; Load exclusion lower bound
CONST_LOAD 0x8FFF   ; Load exclusion upper bound
RANGE_CHECK 0x02    ; Check if in forbidden range
NOT                 ; Invert result
ASSERT              ; Assert true (not in range) or trap
```

## 2. COMPOUND CONSTRAINTS

### 2.1 Logical AND

```guard
GUARD (engine_temp IN [70, 90] AND oil_pressure IN [30, 80])
  SEVERITY CRITICAL
  STANDARD 'ISO 26262 ASIL D'
```

**Semantics:** Both sub-constraints must be satisfied simultaneously.

**Physical Analogy:** Engine operating window - both temperature AND pressure must be normal.

**Compiled Bytecode:**
```flux-c
; Check engine_temp constraint
CONST_LOAD 70       ; Lower bound
CONST_LOAD 90       ; Upper bound
RANGE_CHECK 0x03    ; engine_temp variable ID
; Stack: [temp_ok]

; Check oil_pressure constraint
CONST_LOAD 30       ; Lower bound
CONST_LOAD 80       ; Upper bound
RANGE_CHECK 0x04    ; oil_pressure variable ID
; Stack: [temp_ok, pressure_ok]

BOOL_AND            ; Logical AND
; Stack: [both_ok]
ASSERT              ; Assert or trap
```

### 2.2 Logical OR

```guard
GUARD (backup_power_a IN [11.5, 12.5] OR backup_power_b IN [11.5, 12.5])
  SEVERITY WARNING
  STANDARD 'DO-178C DAL B'
```

**Semantics:** At least one sub-constraint must be satisfied.

**Physical Analogy:** Redundant power supplies - either one can maintain system operation.

**Compiled Bytecode:**
```flux-c
; Check backup_power_a
CONST_LOAD 115      ; 11.5 scaled by 10
CONST_LOAD 125      ; 12.5 scaled by 10
RANGE_CHECK 0x05    ; backup_power_a variable ID

; Check backup_power_b
CONST_LOAD 115
CONST_LOAD 125
RANGE_CHECK 0x06    ; backup_power_b variable ID

BOOL_OR             ; Logical OR
ASSERT              ; Assert or trap
```

### 2.3 Implication

```guard
GUARD (altitude > 10000 IMPLIES cabin_pressure IN [11.3, 14.7])
  SEVERITY CRITICAL
  STANDARD 'FAR 25.841'
```

**Semantics:** If antecedent is true, consequent must also be true.

**Physical Analogy:** Cabin pressurization - above 10,000ft, cabin must be pressurized.

**Compiled Bytecode:**
```flux-c
; Check if altitude > 10000
CONST_LOAD 10000
GT                  ; altitude > 10000
; Stack: [condition]

; If true, check cabin pressure constraint
CONST_LOAD 113      ; 11.3 scaled by 10
CONST_LOAD 147      ; 14.7 scaled by 10
RANGE_CHECK 0x07    ; cabin_pressure variable ID
; Stack: [condition, pressure_ok]

; Implement implication: NOT condition OR consequent
SWAP                ; [pressure_ok, condition]
NOT                 ; [pressure_ok, NOT condition]
BOOL_OR             ; [NOT condition OR pressure_ok]
ASSERT              ; Assert implication holds
```

### 2.4 Negation

```guard
GUARD NOT (brake_pressure EQUAL 0 AND speed GT 50)
  SEVERITY CRITICAL
  STANDARD 'ISO 26262 ASIL D'
```

**Semantics:** The negation of the compound expression must be true.

**Physical Analogy:** Impossible state - cannot have no brakes while moving fast.

**Compiled Bytecode:**
```flux-c
; Check brake_pressure == 0
CONST_LOAD 0
EQ
; Stack: [brakes_off]

; Check speed > 50
CONST_LOAD 50
GT
; Stack: [brakes_off, moving_fast]

BOOL_AND            ; Both conditions true
; Stack: [dangerous_state]
NOT                 ; Negate the dangerous state
; Stack: [safe_state]
ASSERT              ; Assert safe state
```

## 3. TEMPORAL CONSTRAINTS

### 3.1 Rate of Change Limiting

```guard
GUARD RATE_OF_CHANGE(steering_angle, 15)
  SEVERITY WARNING
  STANDARD 'ISO 26262 ASIL B'
  UNIT 'degrees/second'
```

**Semantics:** Rate of change must not exceed 15 units per sampling period.

**Physical Analogy:** Maximum steering rate to prevent vehicle instability.

**Compiled Bytecode:**
```flux-c
CONST_LOAD 15       ; Maximum rate
RATE_CHECK 0x08     ; steering_angle variable ID
ASSERT              ; Assert rate within bounds
```

**Implementation:** RATE_CHECK opcode maintains previous value and computes delta automatically.

### 3.2 Persistence Requirements

```guard
GUARD PERSISTENCE(engine_oil_low, 5)
  SEVERITY WARNING
  STANDARD 'SAE J1939'
```

**Semantics:** Condition must remain true for 5 consecutive samples before triggering.

**Physical Analogy:** Oil pressure warning with debouncing to prevent false alarms.

**Compiled Bytecode:**
```flux-c
CONST_LOAD 5        ; Required persistence count
PERSIST_CHECK 0x09  ; engine_oil_low variable ID
ASSERT              ; Assert persistence achieved
```

**Implementation:** PERSIST_CHECK maintains sample counter for each variable.

### 3.3 Deadband Filtering

```guard
GUARD DEADBAND(sensor_reading, 2.0)
  SEVERITY CAUTION
  STANDARD 'IEC 61508 SIL 2'
  UNIT 'volts'
```

**Semantics:** Suppress changes smaller than deadband threshold to reduce noise.

**Physical Analogy:** Thermostat deadband prevents rapid on/off cycling.

**Compiled Bytecode:**
```flux-c
CONST_LOAD 20       ; 2.0 scaled by 10
DEADBAND 0x0A       ; sensor_reading variable ID
; No assertion - deadband is filtering, not constraint
```

### 3.4 Sequence Ordering

```guard
GUARD SEQUENCE(ignition_on BEFORE fuel_pump_on WITHIN 500ms)
  SEVERITY CRITICAL
  STANDARD 'ISO 26262 ASIL D'
```

**Semantics:** Event A must occur before event B within time window.

**Physical Analogy:** Ignition must precede fuel pump to prevent unsafe conditions.

**Compiled Bytecode:**
```flux-c
CONST_LOAD 500      ; Time window in milliseconds
SEQUENCE_CHECK 0x0B 0x0C ; ignition_on, fuel_pump_on event IDs
ASSERT              ; Assert proper sequence
```

## 4. CROSS-SENSOR CONSTRAINTS

### 4.1 Multi-Variable Conditions

```guard
GUARD ((temp > 80 AND pressure > 50) IMPLIES shutdown_valve EQUAL 1)
  SEVERITY CRITICAL
  STANDARD 'ASME BPVC Section VIII'
```

**Semantics:** High temperature AND pressure requires safety valve activation.

**Physical Analogy:** Pressure vessel safety - overpressure triggers relief valve.

**Compiled Bytecode:**
```flux-c
; Check temp > 80
CONST_LOAD 80
GT
; Stack: [temp_high]

; Check pressure > 50
CONST_LOAD 50
GT
; Stack: [temp_high, pressure_high]

BOOL_AND            ; Both conditions
; Stack: [danger_state]

; Check shutdown valve state
CONST_LOAD 1
EQ                  ; shutdown_valve == 1
; Stack: [danger_state, valve_closed]

; Implement implication
SWAP                ; [valve_closed, danger_state]
NOT                 ; [valve_closed, NOT danger_state]
BOOL_OR             ; [NOT danger_state OR valve_closed]
ASSERT              ; Assert implication
```

### 4.2 Arithmetic Constraints

```guard
GUARD SUM([wheel_speed_fl, wheel_speed_fr, wheel_speed_rl, wheel_speed_rr]) IN [0, 400]
  SEVERITY WARNING
  STANDARD 'ISO 26262 ASIL B'
  UNIT 'rpm'
```

**Semantics:** Sum of all wheel speeds must be within bounds.

**Physical Analogy:** Total wheel speed sanity check for vehicle dynamics.

**Compiled Bytecode:**
```flux-c
; Add all wheel speeds
ADD                 ; fl + fr
ADD                 ; (fl+fr) + rl
ADD                 ; (fl+fr+rl) + rr
; Stack: [total_speed]

; Check range
CONST_LOAD 0        ; Lower bound
CONST_LOAD 400      ; Upper bound
RANGE_CHECK 0xFF    ; Use stack value instead of variable
ASSERT              ; Assert within bounds
```

### 4.3 Tolerance Stack Analysis

```guard
GUARD (part_a_dim + part_b_dim + part_c_dim) IN [99.5, 100.5]
  SEVERITY WARNING
  STANDARD 'ASME Y14.5-2018'
  UNIT 'millimeters'
  SCALE 10
```

**Semantics:** Assembly tolerance stack must remain within specification.

**Physical Analogy:** Mechanical tolerance stackup in precision assembly.

**Compiled Bytecode:**
```flux-c
; Load dimension variables and add
ADD                 ; part_a + part_b
ADD                 ; (part_a+part_b) + part_c
; Stack: [total_dimension]

; Check tolerance bounds (scaled by 10)
CONST_LOAD 995      ; 99.5 * 10
CONST_LOAD 1005     ; 100.5 * 10
RANGE_CHECK 0xFF    ; Check stack value
ASSERT              ; Assert within tolerance
```

## 5. SEVERITY ANNOTATIONS

### 5.1 Criticality Levels

```guard
SEVERITY CRITICAL   # System failure, immediate action required
SEVERITY WARNING    # Degraded operation, monitor closely
SEVERITY CAUTION    # Potential issue, normal operation continues
```

**Mapping to Actions:**
- `CRITICAL`: Immediate system shutdown/safe mode
- `WARNING`: Log event, notify operator, continue operation
- `CAUTION`: Log event for maintenance analysis

### 5.2 Safety Standards Traceability

```guard
STANDARD 'DO-178C DAL A'     # Aviation software, highest criticality
STANDARD 'ISO 26262 ASIL D'  # Automotive, highest safety integrity
STANDARD 'IEC 61508 SIL 4'   # Industrial, highest safety level
STANDARD 'FDA 510(k)'        # Medical device approval
STANDARD 'MISRA-C 2012'      # C coding guidelines
```

**Traceability:** Each standard reference links to specific requirement clauses for certification audit trails.

## 6. PHYSICAL SCALING

### 6.1 Fixed-Point Scaling

```guard
GUARD sensor_voltage IN [3.0, 3.6]
  SCALE 1000        # Store as millivolts (3000-3600)
  UNIT 'volts'
```

**Rationale:** Embedded systems use integer arithmetic. Scale factor converts floating-point specifications to integer implementation.

**Example:** 3.3V becomes 3300 when scaled by 1000.

### 6.2 Unit Documentation

```guard
UNIT 'degrees_C'      # Temperature
UNIT 'pascals'        # Pressure
UNIT 'meters/second'  # Velocity
UNIT 'radians/second' # Angular velocity
UNIT 'amperes'        # Current
UNIT 'volts'          # Voltage
```

**Purpose:** Human-readable documentation. Not enforced by compiler but essential for system understanding.

## 7. COMPILATION TO FLUX-C

### 7.1 Constraint Compilation Pipeline

```
GUARD DSL Source → Parser → AST → Optimizer → FLUX-C Bytecode
```

**Optimization Passes:**
1. Constant folding
2. Dead code elimination
3. Common subexpression elimination
4. Range analysis for bounds checking

### 7.2 Bytecode Generation Examples

**Simple Range Check:**
```guard
GUARD x IN [10, 20]
```
↓
```flux-c
CONST_LOAD 10       ; 0x01 0x0A
CONST_LOAD 20       ; 0x01 0x14
RANGE_CHECK 0x01    ; 0x42 0x01
ASSERT              ; 0x43
```

**Complex Expression:**
```guard
GUARD (a > 5 AND b < 10) OR c EQUAL 42
```
↓
```flux-c
; Evaluate a > 5
CONST_LOAD 5        ; 0x01 0x05
GT                  ; 0x33
; Stack: [a>5]

; Evaluate b < 10
CONST_LOAD 10       ; 0x01 0x0A
LT                  ; 0x32
; Stack: [a>5, b<10]

; Combine with AND
BOOL_AND            ; 0x40
; Stack: [a>5 AND b<10]

; Evaluate c == 42
CONST_LOAD 42       ; 0x01 0x2A
EQ                  ; 0x30
; Stack: [a>5 AND b<10, c==42]

; Combine with OR
BOOL_OR             ; 0x41
; Stack: [result]

ASSERT              ; 0x43
```

### 7.3 Memory Layout

**Bytecode Format:**
- Header: 4 bytes (version, flags, entry_point, checksum)
- Constants Pool: Variable length
- Instruction Sequence: Variable length
- Variable Map: Variable length

**Example Binary:**
```
[HEADER]     01 00 10 00    # Version 1.0, entry at 0x10
[CONSTANTS]  05 0A 14 2A    # 5, 10, 20, 42
[CODE]       01 05 33 01    # CONST_LOAD 5, GT, CONST_LOAD 10
             0A 32 40 01    # 10, LT, BOOL_AND, CONST_LOAD
             2A 30 41 43    # 42, EQ, BOOL_OR, ASSERT
[VARMAP]     78 00 79 01    # x->0x78, y->0x79, ...
```

## 8. FORMAL GRAMMAR (BNF)

```bnf
<guard_program>   ::= <guard_stmt>+

<guard_stmt>      ::= "GUARD" <constraint> <annotation>*

<constraint>      ::= <basic_constraint>
                    | <compound_constraint>
                    | <temporal_constraint>
                    | <cross_sensor_constraint>

<basic_constraint> ::= <identifier> "IN" <range>
                     | <identifier> "EQUAL" <value>
                     | <identifier> "NOT_IN" <range>

<compound_constraint> ::= "(" <constraint> "AND" <constraint> ")"
                        | "(" <constraint> "OR" <constraint> ")"
                        | "(" <constraint> "IMPLIES" <constraint> ")"
                        | "NOT" "(" <constraint> ")"

<temporal_constraint> ::= "RATE_OF_CHANGE" "(" <identifier> "," <value> ")"
                        | "PERSISTENCE" "(" <identifier> "," <integer> ")"
                        | "DEADBAND" "(" <identifier> "," <value> ")"
                        | "SEQUENCE" "(" <event> "BEFORE" <event> "WITHIN" <time> ")"

<cross_sensor_constraint> ::= "SUM" "(" <identifier_list> ")" "IN" <range>
                             | <arithmetic_expr> <relop> <value>

<annotation>      ::= "SEVERITY" <severity_level>
                    | "STANDARD" <standard_ref>
                    | "UNIT" <unit_string>
                    | "SCALE" <scale_factor>

<range>           ::= "[" <value> "," <value> "]"
<value>           ::= <number> | <identifier>
<identifier>      ::= [a-zA-Z_][a-zA-Z0-9_]*
<severity_level>  ::= "CRITICAL" | "WARNING" | "CAUTION"
<standard_ref>    ::= "'" <string> "'"
<unit_string>     ::= "'" <string> "'"
<relop>           ::= ">" | "<" | ">=" | "<=" | "==" | "!="
```

## 9. PHYSICAL ANALOGIES REFERENCE

| Software Constraint | Physical Analog | Engineering Domain |
|---------------------|-----------------|-------------------|
| Range bounds | Tolerance limits | Mechanical engineering |
| Rate limiting | Speed governors | Mechanical systems |
| Persistence | Filtering/damping | Control systems |
| Sequence ordering | Interlock systems | Safety engineering |
| Implication | Cause-effect chains | Systems engineering |
| Deadband | Hysteresis | Control theory |
| Tolerance stacks | Dimensional chains | Manufacturing |
| Cross-coupling | Multi-physics | System dynamics |

**Key Insight:** Every software constraint maps to well-understood physical engineering principles, enabling knowledge transfer between domains.

## 10. CERTIFICATION COMPLIANCE

### 10.1 DO-178C (Aviation)

**Requirements:**
- Traceability: Each GUARD statement links to system requirement
- Verification: Formal proof of constraint satisfaction
- Testing: Boundary value testing for all ranges

**Example Compliance:**
```guard
GUARD airspeed IN [60, 250]
  SEVERITY CRITICAL
  STANDARD 'DO-178C DAL A Req 3.2.1'
  VERIFICATION 'Formal proof attached'
  TEST_CASES 'TC_001, TC_002, TC_003'
```

### 10.2 ISO 26262 (Automotive)

**Requirements:**
- ASIL classification for each constraint
- Fault injection testing
- Hardware/software co-verification

### 10.3 IEC 61508 (Industrial)

**Requirements:**
- SIL level assignment
- Common cause failure analysis
- Systematic capability evaluation

## Conclusion

The GUARD DSL provides a formal, verifiable language for specifying constraints in safety-critical embedded systems. By mapping software constraints to physical engineering principles and compiling to deterministic bytecode, GUARD enables both human understanding and machine verification of system safety properties.

**Next Steps:**
1. Implement GUARD compiler targeting FLUX-C
2. Develop formal verification toolchain
3. Create certification evidence packages
4. Build IDE integration for constraint development

---
*This reference serves as the authoritative specification for GUARD DSL implementation and compliance.*