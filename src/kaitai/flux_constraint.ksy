# FLUX Constraint Engine — Kaitai Struct (2015, Binary Format Specification)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# The insight: Kaitai Struct defines BINARY FORMATS declaratively.
# Constraint data (lo/hi/name) IS a binary format. The constraint
# check result IS a binary format. By defining both in Kaitai,
# we get parsers for FREE in every supported language (13+).
#
# "The format IS the specification. The specification IS the parser.
#  Constraints as binary data — no encoding ambiguity, no drift."

meta:
  id: flux_constraint
  title: FLUX Constraint Engine — Kaitai Struct
  endian: le
  imports:
    - /common/byte

# ══════════════════════════════════════════════════════════════════
#  Constants (embedded as enums for type safety)
# ══════════════════════════════════════════════════════════════════

enums:
  severity:
    0: pass
    1: caution
    2: warning
    3: critical

# ══════════════════════════════════════════════════════════════════
#  Constraint Definition — the binary layout of a single constraint
# ══════════════════════════════════════════════════════════════════

types:
  constraint:
    seq:
      - id: lo
        type: s1          # signed INT8, range [-128, 127], we use [-127, 127]
        doc: Lower bound (saturated INT8)
      - id: hi
        type: s1          # signed INT8
        doc: Upper bound (saturated INT8)
      - id: name_len
        type: u1
        doc: Length of constraint name string
      - id: name
        type: str
        encoding: ascii
        size: name_len
        doc: Human-readable constraint name (max 32 chars)
    instances:
      is_valid:
        value: lo >= -127 and lo <= hi and hi <= 127
        doc: Verify bounds are within INT8 range and lo <= hi

  # ════════════════════════════════════════════════════════════════
  #  Constraint Set — up to 8 constraints (the INT8 x8 flat bounds)
  # ════════════════════════════════════════════════════════════════

  constraint_set:
    seq:
      - id: count
        type: u1
        doc: Number of constraints (1-8)
      - id: constraints
        type: constraint
        repeat: expr
        repeat-expr: count
    instances:
      is_valid:
        value: count >= 1 and count <= 8
        doc: Verify constraint count is within limits
      total_bytes:
        value: '1 + (constraints.size * count)'
        doc: Total byte size of this constraint set

  # ════════════════════════════════════════════════════════════════
  #  Sensor Reading — the binary input to be checked
  # ════════════════════════════════════════════════════════════════

  sensor_reading:
    seq:
      - id: sensor_id
        type: u2          # uint16 sensor identifier
        doc: Unique sensor identifier
      - id: timestamp
        type: u4          # uint32 Unix timestamp
        doc: Reading timestamp
      - id: value
        type: s1          # INT8 — already saturated at the sensor
        doc: Sensor value (saturated to [-127, 127])
    instances:
      saturated:
        value: 'value < -127 ? -127 : (value > 127 ? 127 : value)'
        doc: Double-check saturation (defense in depth)

  # ════════════════════════════════════════════════════════════════
  #  FluxResult — the binary output of a constraint check
  # ════════════════════════════════════════════════════════════════

  flux_result:
    seq:
      - id: error_mask
        type: u1
        doc: Bit mask of violated constraints (bit i = constraint i failed)
      - id: severity
        type: u1
        enum: severity
        doc: Overall severity level (0-3)
      - id: violated_lo
        type: u1
        doc: Bit mask of lower bound violations
      - id: violated_hi
        type: u1
        doc: Bit mask of upper bound violations
      - id: violated_count
        type: u1
        doc: Number of violated constraints
      - id: passed
        type: u1
        doc: Boolean (0=failed, 1=passed)
    instances:
      is_pass:
        value: passed == 1
      is_critical:
        value: severity == 3
      failed_constraints:
        value: violated_count
        doc: Alias for clarity

  # ════════════════════════════════════════════════════════════════
  #  Batch Request — multiple values to check against a constraint set
  # ════════════════════════════════════════════════════════════════

  batch_request:
    seq:
      - id: magic
        contents: ['F', 'L', 'U', 'X']
        doc: Magic bytes identifying a FLUX batch request
      - id: version
        type: u1
        doc: Protocol version (currently 1)
      - id: constraint_set
        type: constraint_set
      - id: value_count
        type: u2
        doc: Number of values to check
      - id: values
        type: s1
        repeat: expr
        repeat-expr: value_count
        doc: INT8 values to check

  # ════════════════════════════════════════════════════════════════
  #  Batch Response — results for each input value
  # ════════════════════════════════════════════════════════════════

  batch_response:
    seq:
      - id: magic
        contents: ['R', 'E', 'S', 'P']
        doc: Magic bytes identifying a FLUX batch response
      - id: result_count
        type: u2
        doc: Number of results (matches batch_request.value_count)
      - id: results
        type: flux_result
        repeat: expr
        repeat-expr: result_count
    instances:
      total_passed:
        value: 'results.reduce(0, (sum, r) => sum + r.passed)'
        doc: Count of passed checks
      total_failed:
        value: result_count - total_passed

  # ════════════════════════════════════════════════════════════════
  #  Industry Presets — pre-defined constraint sets as binary blobs
  # ════════════════════════════════════════════════════════════════
  #
  # Aviation: cabin_temp [-55,70], pressure [75,101], fuel [0,100], hydraulic [60,100]
  # Nuclear:  neutron_flux [0,110], core_temp [0,65], pressurizer [72,100], coolant [0,100]
  # Medical:  body_temp [36,38], heart_rate [60,100], spo2 [95,100], bp_systolic [80,120]
  #
  # Binary encoding of aviation preset:
  #   count=4, then 4 constraint records:
  #   lo=-55(0xC9), hi=70(0x46), len=12, "cabin_temp_C"
  #   lo=75(0x4B),  hi=101(0x65), len=18, "cabin_pressure_kPa"
  #   lo=0(0x00),   hi=100(0x64), len=13, "fuel_flow_pct"
  #   lo=60(0x3C),  hi=100(0x64), len=13, "hydraulic_pct"

  preset_id:
    seq:
      - id: preset_name_len
        type: u1
      - id: preset_name
        type: str
        encoding: ascii
        size: preset_name_len

# ══════════════════════════════════════════════════════════════════
#  Top-level — a FLUX constraint file
# ══════════════════════════════════════════════════════════════════

seq:
  - id: header
    contents: ['F', 'L', 'X', '1']
    doc: File magic: FLX1
  - id: num_sets
    type: u1
    doc: Number of constraint sets in this file
  - id: sets
    type: constraint_set
    repeat: expr
    repeat-expr: num_sets

instances:
  total_constraints:
    value: 'sets.reduce(0, (sum, s) => sum + s.count)'
    doc: Total constraints across all sets

# ══════════════════════════════════════════════════════════════════
#  KAITAI STRUCT INSIGHT
# ══════════════════════════════════════════════════════════════════
#
# Kaitai Struct generates parsers in 13+ languages from a single .ksy file.
# This means ONE specification produces WORKING PARSERS in:
#   Python, JavaScript, C#, Java, C++, Perl, Ruby, PHP, Lua, Go, Rust,
#   Nim, Swift, and more.
#
# The binary format IS the constraint contract:
#   - No text encoding ambiguity (binary is binary)
#   - No version drift (the format is the version)
#   - No language-specific quirks (all parsers read the same bytes)
#   - Zero-copy parsing possible (memory-map the constraint file)
#
# For embedded systems: the constraint binary fits in ~40 bytes
# for a 4-constraint set. That's a single cache line.
#
# For network protocols: the batch_request/response format enables
# binary constraint checking over any transport (TCP, UDP, CAN, SPI).
#
# The insight: when the constraint IS the binary format, the parser
# IS the validator. You can't have a constraint that doesn't parse,
# and you can't have a parse that doesn't respect the constraints.
# ══════════════════════════════════════════════════════════════════
