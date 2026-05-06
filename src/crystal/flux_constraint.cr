# FLUX Constraint Engine — Crystal
# Pure INT8 saturated constraint checking. Zero dependencies.

INT8_MIN = -127
INT8_MAX = 127

enum Severity
  Pass = 0; Caution = 1; Warning = 2; Critical = 3
end

record Constraint, lo : Int32, hi : Int32, name : String = "" do
  def sat_lo; Math.max(INT8_MIN, Math.min(INT8_MAX, lo)); end
  def sat_hi; Math.max(INT8_MIN, Math.min(INT8_MAX, hi)); end
end

record FluxResult,
  error_mask : Int32, severity : Severity,
  violated_lo : Int32, violated_hi : Int32,
  violated_count : Int32, passed : Bool

class FluxChecker
  getter constraints : Array(Constraint)

  def initialize(@constraints : Array(Constraint))
    raise "Non-empty constraints required" if @constraints.empty?
    raise "Max 8 constraints" if @constraints.size > 8
  end

  def check(value : Int) : FluxResult
    val = self.class.saturate(value)
    error_mask = 0; violated_lo = 0; violated_hi = 0; violated_count = 0

    constraints.each_with_index do |c, i|
      lo_fail = val < c.sat_lo
      hi_fail = val > c.sat_hi
      if lo_fail || hi_fail
        error_mask |= (1 << i)
        violated_count += 1
      end
      violated_lo |= (1 << i) if lo_fail
      violated_hi |= (1 << i) if hi_fail
    end

    nc = constraints.size
    sev = if violated_count == 0; Severity::Pass
           elsif violated_count <= nc // 4; Severity::Caution
           elsif violated_count <= nc // 2; Severity::Warning
           else; Severity::Critical
           end

    FluxResult.new(error_mask, sev, violated_lo, violated_hi, violated_count, sev == Severity::Pass)
  end

  def check_batch(values : Array(Int)) : Tuple(Array(FluxResult), Hash(String, Int32))
    results = values.map { |v| check(v) }
    stats = {
      "pass"     => results.count(&.severity.pass?),
      "caution"  => results.count(&.severity.caution?),
      "warning"  => results.count(&.severity.warning?),
      "critical" => results.count(&.severity.critical?),
    }
    {results, stats}
  end

  def self.saturate(v : Int) : Int32
    v < INT8_MIN ? INT8_MIN : (v > INT8_MAX ? INT8_MAX : v.to_i32)
  end

  PRESETS = {
    "aviation" => [
      Constraint.new(-55, 70, "cabin_temp_C"),
      Constraint.new(75, 101, "cabin_pressure_kPa"),
      Constraint.new(0, 100, "fuel_flow_pct"),
      Constraint.new(60, 100, "hydraulic_pct"),
    ],
    "medical" => [
      Constraint.new(36, 38, "body_temp_C"),
      Constraint.new(60, 100, "heart_rate_bpm"),
      Constraint.new(95, 100, "spo2_pct"),
      Constraint.new(80, 120, "bp_systolic_mmHg"),
    ],
    "automotive" => [
      Constraint.new(-40, 60, "battery_temp_C"),
      Constraint.new(0, 100, "soc_pct"),
      Constraint.new(0, 100, "charge_rate_pct"),
      Constraint.new(20, 80, "cabin_temp_C"),
    ],
    "energy" => [
      Constraint.new(49, 51, "grid_freq_Hz_x10"),
      Constraint.new(95, 105, "voltage_pct"),
      Constraint.new(0, 80, "transformer_temp_C"),
      Constraint.new(0, 100, "line_load_pct"),
    ],
  }

  def self.from_preset(name : String) : FluxChecker
    cs = PRESETS[name]?
    raise "Unknown preset: #{name}" unless cs
    new(cs)
  end
end

# Self-test
if PROGRAM_NAME.includes?("flux_constraint")
  puts "FLUX Constraint Engine — Crystal"
  puts "================================"
  raise "sat" unless FluxChecker.saturate(-128) == -127
  raise "sat" unless FluxChecker.saturate(128) == 127
  puts "  saturate: OK"
  fc = FluxChecker.new([Constraint.new(0, 100, "test")])
  raise "pass" unless fc.check(50).passed
  raise "fail" if fc.check(150).passed
  puts "  check: OK"
  fc4 = FluxChecker.new([Constraint.new(0,10)] * 4)
  r = fc4.check(50)
  raise "sev" unless r.severity.critical? && r.violated_count == 4
  puts "  severity: OK"
  fc3 = FluxChecker.from_preset("aviation")
  raise "preset" unless fc3.constraints.size == 4
  puts "  presets: OK"
  puts "  All tests pass"
end
