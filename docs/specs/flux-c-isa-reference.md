# FLUX-C Instruction Set Architecture Reference

**Version:** 1.0
**Target Platform:** ARM Cortex-R5 (180MHz, 512KB RAM, 2MB Flash)
**Execution Model:** Stack-based virtual machine with safety constraints

## Overview

FLUX-C (Formal Language for Unified eXecution - Constraints) is a specialized bytecode instruction set designed for executing safety-critical constraint verification in real-time embedded systems. The ISA prioritizes deterministic timing, minimal memory footprint, and formal verifiability.

**Design Principles:**
- **Deterministic Timing:** Every instruction has predictable cycle count
- **Stack-Based:** No register allocation complexity
- **Safety-First:** Built-in constraint checking and sandboxing
- **Minimal Footprint:** 42 opcodes, 8-bit instruction format
- **Real-Time:** Sub-microsecond execution guarantees

## Encoding Format

### Instruction Format

```
Byte 0: [OPCODE] (8 bits)
Byte 1+: [OPERAND] (optional, variable length)
```

**Opcode Distribution:**
- 0x00-0x0F: Stack operations (16 slots, 4 used)
- 0x10-0x2F: Arithmetic operations (32 slots, 7 used)
- 0x30-0x4F: Comparison operations (32 slots, 9 used)
- 0x50-0x5F: Boolean operations (16 slots, 3 used)
- 0x60-0x6F: Constraint operations (16 slots, 4 used)
- 0x70-0x7F: Control flow (16 slots, 6 used)
- 0x80-0xFF: System operations (128 slots, 9 used)

### Operand Encoding

- **Immediate Values:** 1-4 bytes, little-endian
- **Variable IDs:** 1 byte (0x00-0xFF)
- **Jump Offsets:** 2 bytes, signed, relative to PC
- **Function IDs:** 1 byte

## Program Format

```
[HEADER - 8 bytes]
  Magic: 0xFLUX (4 bytes)
  Version: 0x0100 (2 bytes)
  Entry Point: offset (2 bytes)

[CONSTANTS POOL - Variable]
  Count: N (2 bytes)
  Constant[0]: value (4 bytes)
  ...
  Constant[N-1]: value (4 bytes)

[VARIABLE MAP - Variable]
  Count: M (2 bytes)
  Variable[0]: {ID, Name, Type} (variable length)
  ...
  Variable[M-1]: {ID, Name, Type}

[CODE SECTION - Variable]
  Instruction[0]: opcode + operands
  ...
  Instruction[N-1]: opcode + operands

[CHECKSUM - 4 bytes]
  CRC32 of entire program
```

## Execution Model

### Stack Machine

- **Stack Size:** 256 entries max (safety limit)
- **Entry Size:** 32-bit signed integers
- **Overflow Protection:** Hardware stack overflow detection
- **Underflow Protection:** Stack underflow triggers GUARD_TRAP

### Variable Storage

- **Global Variables:** 256 max, ID 0x00-0xFF
- **Local Variables:** Function-scoped, stack-allocated
- **Type System:** int32, boolean, constraint_result

### Timing Model

All cycle counts assume ARM Cortex-R5 at 180MHz, cached execution.

---

# INSTRUCTION SET REFERENCE

## Stack Operations (0x00-0x0F)

### 0x01 PUSH `value`
**Stack:** [] → [value]
**Cycles:** 2
**Operand:** 4-byte immediate value

Pushes immediate 32-bit value onto stack.

**Example:**
```flux-c
PUSH 42        ; 0x01 0x2A 0x00 0x00 0x00
```

### 0x02 POP
**Stack:** [value] → []
**Cycles:** 1
**Operand:** None

Removes top value from stack and discards it.

**Example:**
```flux-c
PUSH 10        ; Stack: [10]
PUSH 20        ; Stack: [10, 20]
POP            ; Stack: [10]
```

### 0x03 DUP
**Stack:** [value] → [value, value]
**Cycles:** 1
**Operand:** None

Duplicates top stack value.

**Example:**
```flux-c
PUSH 42        ; Stack: [42]
DUP            ; Stack: [42, 42]
```

### 0x04 SWAP
**Stack:** [a, b] → [b, a]
**Cycles:** 1
**Operand:** None

Swaps top two stack values.

**Example:**
```flux-c
PUSH 10        ; Stack: [10]
PUSH 20        ; Stack: [10, 20]
SWAP           ; Stack: [20, 10]
```

---

## Arithmetic Operations (0x10-0x2F)

### 0x10 ADD
**Stack:** [a, b] → [a + b]
**Cycles:** 2
**Operand:** None

Adds top two stack values. Overflow checking enabled.

**Example:**
```flux-c
PUSH 15        ; Stack: [15]
PUSH 27        ; Stack: [15, 27]
ADD            ; Stack: [42]
```

### 0x11 SUB
**Stack:** [a, b] → [a - b]
**Cycles:** 2
**Operand:** None

Subtracts b from a. Underflow checking enabled.

**Example:**
```flux-c
PUSH 50        ; Stack: [50]
PUSH 8         ; Stack: [50, 8]
SUB            ; Stack: [42]
```

### 0x12 MUL
**Stack:** [a, b] → [a × b]
**Cycles:** 4
**Operand:** None

Multiplies top two stack values. Overflow checking enabled.

**Example:**
```flux-c
PUSH 6         ; Stack: [6]
PUSH 7         ; Stack: [6, 7]
MUL            ; Stack: [42]
```

### 0x13 DIV
**Stack:** [a, b] → [a ÷ b]
**Cycles:** 12
**Operand:** None

Divides a by b (integer division). Division by zero triggers GUARD_TRAP.

**Example:**
```flux-c
PUSH 84        ; Stack: [84]
PUSH 2         ; Stack: [84, 2]
DIV            ; Stack: [42]
```

### 0x14 MOD
**Stack:** [a, b] → [a mod b]
**Cycles:** 14
**Operand:** None

Computes a modulo b. Division by zero triggers GUARD_TRAP.

**Example:**
```flux-c
PUSH 100       ; Stack: [100]
PUSH 58        ; Stack: [100, 58]
MOD            ; Stack: [42]
```

### 0x15 NEG
**Stack:** [a] → [-a]
**Cycles:** 1
**Operand:** None

Negates top stack value.

**Example:**
```flux-c
PUSH 42        ; Stack: [42]
NEG            ; Stack: [-42]
```

### 0x16 ABS
**Stack:** [a] → [|a|]
**Cycles:** 2
**Operand:** None

Computes absolute value of top stack value.

**Example:**
```flux-c
PUSH -42       ; Stack: [-42]
ABS            ; Stack: [42]
```

---

## Comparison Operations (0x30-0x4F)

### 0x30 EQ
**Stack:** [a, b] → [a == b ? 1 : 0]
**Cycles:** 2
**Operand:** None

Equality comparison. Result is 1 (true) or 0 (false).

**Example:**
```flux-c
PUSH 42        ; Stack: [42]
PUSH 42        ; Stack: [42, 42]
EQ             ; Stack: [1]
```

### 0x31 NEQ
**Stack:** [a, b] → [a != b ? 1 : 0]
**Cycles:** 2
**Operand:** None

Inequality comparison.

### 0x32 LT
**Stack:** [a, b] → [a < b ? 1 : 0]
**Cycles:** 2
**Operand:** None

Less-than comparison.

**Example:**
```flux-c
PUSH 30        ; Stack: [30]
PUSH 50        ; Stack: [30, 50]
LT             ; Stack: [1]
```

### 0x33 GT
**Stack:** [a, b] → [a > b ? 1 : 0]
**Cycles:** 2
**Operand:** None

Greater-than comparison.

### 0x34 LTE
**Stack:** [a, b] → [a <= b ? 1 : 0]
**Cycles:** 2
**Operand:** None

Less-than-or-equal comparison.

### 0x35 GTE
**Stack:** [a, b] → [a >= b ? 1 : 0]
**Cycles:** 2
**Operand:** None

Greater-than-or-equal comparison.

### 0x36 MIN
**Stack:** [a, b] → [min(a, b)]
**Cycles:** 3
**Operand:** None

Returns minimum of two values.

**Example:**
```flux-c
PUSH 42        ; Stack: [42]
PUSH 100       ; Stack: [42, 100]
MIN            ; Stack: [42]
```

### 0x37 MAX
**Stack:** [a, b] → [max(a, b)]
**Cycles:** 3
**Operand:** None

Returns maximum of two values.

### 0x38 CLAMP
**Stack:** [value, min, max] → [clamped_value]
**Cycles:** 4
**Operand:** None

Clamps value to range [min, max].

**Example:**
```flux-c
PUSH 150       ; Stack: [150] (value to clamp)
PUSH 0         ; Stack: [150, 0] (minimum)
PUSH 100       ; Stack: [150, 0, 100] (maximum)
CLAMP          ; Stack: [100] (clamped result)
```

---

## Boolean Operations (0x50-0x5F)

### 0x50 BOOL_AND
**Stack:** [a, b] → [a && b ? 1 : 0]
**Cycles:** 2
**Operand:** None

Logical AND. Treats non-zero as true.

**Example:**
```flux-c
PUSH 1         ; Stack: [1] (true)
PUSH 5         ; Stack: [1, 5] (also true)
BOOL_AND       ; Stack: [1] (true)
```

### 0x51 BOOL_OR
**Stack:** [a, b] → [a || b ? 1 : 0]
**Cycles:** 2
**Operand:** None

Logical OR. Treats non-zero as true.

### 0x52 NOT
**Stack:** [a] → [a == 0 ? 1 : 0]
**Cycles:** 1
**Operand:** None

Logical NOT. Returns 1 if input is 0, otherwise 0.

**Example:**
```flux-c
PUSH 0         ; Stack: [0]
NOT            ; Stack: [1]

PUSH 42        ; Stack: [42]
NOT            ; Stack: [0]
```

---

## Constraint Operations (0x60-0x6F)

### 0x60 RANGE_CHECK `var_id`
**Stack:** [min, max] → [in_range ? 1 : 0]
**Cycles:** 5
**Operand:** 1-byte variable ID

Checks if variable value is within range [min, max]. If `var_id` is 0xFF, uses top stack value instead.

**Example:**
```flux-c
PUSH 10        ; Stack: [10] (minimum)
PUSH 50        ; Stack: [10, 50] (maximum)
RANGE_CHECK 0x01 ; Check variable 1 against [10, 50]
               ; Stack: [1] if var1 ∈ [10,50], [0] otherwise
```

### 0x61 BITMASK_CHECK `var_id` `mask`
**Stack:** [] → [masked_result]
**Cycles:** 3
**Operand:** 1-byte variable ID, 4-byte mask

Performs bitwise AND of variable with mask.

**Example:**
```flux-c
BITMASK_CHECK 0x02 0x00FF0000  ; Extract bits 16-23 from var2
                               ; Stack: [masked_value]
```

### 0x62 ASSERT
**Stack:** [condition] → []
**Cycles:** 2
**Operand:** None

Asserts that condition is true (non-zero). Triggers GUARD_TRAP if false.

**Example:**
```flux-c
PUSH 1         ; Stack: [1] (true condition)
ASSERT         ; Stack: [] (assertion passes)

PUSH 0         ; Stack: [0] (false condition)
ASSERT         ; GUARD_TRAP triggered!
```

### 0x63 CHECKPOINT `checkpoint_id`
**Stack:** [] → []
**Cycles:** 10
**Operand:** 1-byte checkpoint ID

Records current state for debugging/rollback. Used in safety-critical systems for state tracking.

**Example:**
```flux-c
CHECKPOINT 0x10  ; Record state at checkpoint 16
```

---

## Control Flow (0x70-0x7F)

### 0x70 JUMP `offset`
**Stack:** [] → []
**Cycles:** 3
**Operand:** 2-byte signed offset

Unconditional relative jump.

**Example:**
```flux-c
JUMP +10       ; Jump forward 10 bytes
JUMP -5        ; Jump backward 5 bytes
```

### 0x71 JUMP_IF `offset`
**Stack:** [condition] → []
**Cycles:** 3
**Operand:** 2-byte signed offset

Jump if top stack value is non-zero (true).

**Example:**
```flux-c
PUSH 1         ; Stack: [1]
JUMP_IF +20    ; Jump taken, stack: []

PUSH 0         ; Stack: [0]
JUMP_IF +20    ; Jump not taken, stack: []
```

### 0x72 CALL `func_id`
**Stack:** [args...] → [return_value]
**Cycles:** 5 + function_cost
**Operand:** 1-byte function ID

Calls function by ID. Function signature determines argument count.

**Example:**
```flux-c
PUSH 10        ; Stack: [10] (argument)
PUSH 20        ; Stack: [10, 20] (argument)
CALL 0x05      ; Call function 5 with 2 args
               ; Stack: [result]
```

### 0x73 RET
**Stack:** [return_value] → [return_value] (in caller)
**Cycles:** 4
**Operand:** None

Returns from function call.

### 0x74 HALT
**Stack:** [] → []
**Cycles:** 1
**Operand:** None

Stops program execution normally.

### 0x75 GUARD_TRAP `severity`
**Stack:** [] → [] (execution stops)
**Cycles:** 20
**Operand:** 1-byte severity code

Triggers constraint violation handler.

**Severity Codes:**
- 0x01: CAUTION (log only)
- 0x02: WARNING (log + notify)
- 0xFF: CRITICAL (immediate shutdown)

**Example:**
```flux-c
PUSH 0         ; Stack: [0] (failure condition)
ASSERT         ; Internally calls GUARD_TRAP 0xFF
```

---

## System Operations (0x80-0xFF)

### 0x80 SANDBOX_ENTER `permissions`
**Stack:** [] → []
**Cycles:** 50
**Operand:** 4-byte permission mask

Enters restricted execution sandbox. Limits available operations.

**Permission Bits:**
- Bit 0: Allow memory access
- Bit 1: Allow I/O operations
- Bit 2: Allow system calls
- Bit 3-31: Reserved

### 0x81 SANDBOX_EXIT
**Stack:** [] → []
**Cycles:** 30
**Operand:** None

Exits current sandbox level. Must be balanced with SANDBOX_ENTER.

### 0x82 DEADLINE `microseconds`
**Stack:** [] → []
**Cycles:** 10
**Operand:** 4-byte deadline in microseconds

Sets execution deadline. GUARD_TRAP triggered if exceeded.

**Example:**
```flux-c
DEADLINE 1000  ; Must complete within 1000 µs
```

### 0x83 CONSTRAINT_ID `id`
**Stack:** [] → []
**Cycles:** 2
**Operand:** 2-byte constraint ID

Associates following operations with constraint ID for traceability.

### 0x84 LOG `level` `message_id`
**Stack:** [] → []
**Cycles:** 25
**Operand:** 1-byte level, 1-byte message ID

Logs event with severity level. Message resolved from message table.

**Log Levels:**
- 0x01: DEBUG
- 0x02: INFO
- 0x03: WARNING
- 0x04: ERROR

### 0x85 REVERT `checkpoint_id`
**Stack:** [any...] → [restored_state]
**Cycles:** 50
**Operand:** 1-byte checkpoint ID

Restores state to specified checkpoint. Used for error recovery.

### 0x86 FLUSH
**Stack:** [] → []
**Cycles:** 100
**Operand:** None

Flushes all pending operations (I/O, logs, etc.) to ensure completion.

### 0x87 NOP
**Stack:** [] → []
**Cycles:** 1
**Operand:** None

No operation. Used for padding and timing alignment.

### 0x88 CONST_LOAD `index`
**Stack:** [] → [constant_value]
**Cycles:** 3
**Operand:** 2-byte constant pool index

Loads constant from constants pool onto stack.

**Example:**
```flux-c
CONST_LOAD 0   ; Load constant[0] onto stack
```

---

# SPECIALIZED INSTRUCTIONS

## Temporal Constraint Support

### RATE_CHECK (Internal - Generated by Compiler)
Implements GUARD RATE_OF_CHANGE by maintaining per-variable state:

```c
struct rate_state {
    int32_t previous_value;
    uint32_t last_timestamp;
    int32_t max_delta;
};
```

### PERSIST_CHECK (Internal - Generated by Compiler)
Implements GUARD PERSISTENCE by maintaining counters:

```c
struct persistence_state {
    uint8_t consecutive_count;
    uint8_t required_count;
    uint8_t last_value;
};
```

### DEADBAND (Internal - Generated by Compiler)
Implements noise filtering:

```c
struct deadband_state {
    int32_t filtered_value;
    int32_t threshold;
};
```

### SEQUENCE_CHECK (Internal - Generated by Compiler)
Implements temporal ordering verification:

```c
struct sequence_state {
    uint32_t event_a_timestamp;
    uint32_t event_b_timestamp;
    uint32_t max_interval_us;
    uint8_t state; // WAITING_A, WAITING_B, COMPLETED, VIOLATED
};
```

---

# PERFORMANCE CHARACTERISTICS

## Cycle Count Summary

| Operation Category | Min Cycles | Max Cycles | Average |
|-------------------|------------|------------|---------|
| Stack operations  | 1          | 2          | 1.5     |
| Arithmetic        | 1          | 14         | 4.6     |
| Comparison        | 2          | 4          | 2.4     |
| Boolean           | 1          | 2          | 1.7     |
| Constraint        | 2          | 10         | 5.0     |
| Control flow      | 1          | 25         | 6.2     |
| System            | 2          | 100        | 31.7    |

## Memory Usage

- **Instruction Memory:** ~2KB typical constraint program
- **Stack Memory:** 256 × 4 bytes = 1KB max
- **Variable Storage:** 256 × 4 bytes = 1KB max
- **State Tables:** ~4KB for temporal constraints
- **Total Runtime:** <8KB typical

## Real-Time Guarantees

- **Maximum Instruction Time:** 100 cycles (FLUSH)
- **Typical Constraint Check:** <20 cycles
- **Context Switch Overhead:** <200 cycles
- **Interrupt Latency:** <50 cycles (FLUX-C is interruptible)

---

# EXAMPLE PROGRAMS

## Simple Range Check

**GUARD DSL:**
```guard
GUARD temperature IN [0, 85]
```

**FLUX-C Bytecode:**
```flux-c
CONST_LOAD 0        ; 0x88 0x00 0x00
CONST_LOAD 1        ; 0x88 0x00 0x01  (constant[1] = 85)
RANGE_CHECK 0x10    ; 0x60 0x10       (temperature = var 0x10)
ASSERT              ; 0x62
HALT                ; 0x74
```

**Binary Encoding:**
```
[HEADER]
46 4C 55 58  01 00  08 00    # FLUX v1.0, entry=8

[CONSTANTS]
02 00                        # 2 constants
00 00 00 00                  # constant[0] = 0
55 00 00 00                  # constant[1] = 85

[VARIABLES]
01 00                        # 1 variable
10 "temperature" 00          # var 0x10 named "temperature"

[CODE] (offset 8)
88 00 00                     # CONST_LOAD 0
88 00 01                     # CONST_LOAD 1
60 10                        # RANGE_CHECK 0x10
62                           # ASSERT
74                           # HALT

[CHECKSUM]
AB CD EF 12                  # CRC32
```

## Complex Multi-Constraint

**GUARD DSL:**
```guard
GUARD (engine_temp IN [70, 90] AND oil_pressure IN [30, 80])
  SEVERITY CRITICAL
```

**FLUX-C Bytecode:**
```flux-c
; Check engine_temp IN [70, 90]
CONST_LOAD 0        ; 70
CONST_LOAD 1        ; 90
RANGE_CHECK 0x20    ; engine_temp
; Stack: [temp_ok]

; Check oil_pressure IN [30, 80]
CONST_LOAD 2        ; 30
CONST_LOAD 3        ; 80
RANGE_CHECK 0x21    ; oil_pressure
; Stack: [temp_ok, pressure_ok]

; Combine with AND
BOOL_AND            ; Stack: [both_ok]

; Assert with CRITICAL severity
ASSERT              ; Triggers GUARD_TRAP 0xFF if false

HALT
```

---

# SAFETY FEATURES

## Stack Protection
- Hardware stack overflow detection
- Automatic underflow protection
- Stack depth limits enforced

## Memory Safety
- All memory access bounds-checked
- No pointer arithmetic allowed
- Sandboxed execution domains

## Timing Safety
- Maximum instruction cycle counts enforced
- Deadline monitoring with DEADLINE instruction
- Real-time scheduler integration

## Fault Tolerance
- Checkpointing for state recovery
- Graceful degradation on constraint violations
- Formal verification of bytecode safety properties

---

# FORMAL VERIFICATION

FLUX-C bytecode is designed for formal verification:

## Properties Verified
1. **Memory Safety:** No buffer overflows or invalid accesses
2. **Timing Bounds:** All instruction sequences have bounded execution time
3. **Stack Safety:** Stack operations never cause overflow/underflow
4. **Constraint Completeness:** All GUARD statements compile to verifiable bytecode
5. **Termination:** All programs are guaranteed to terminate

## Verification Tools
- **Static Analysis:** Pre-execution bytecode verification
- **Model Checking:** Exhaustive state space verification for critical paths
- **Runtime Monitoring:** Dynamic verification during execution

---

*This ISA reference provides the complete specification for FLUX-C implementation, verification, and certification compliance.*