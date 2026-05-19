# FLUX Constraint Engine — Mojo
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# Usage:
#     var checker = FluxChecker(
#         constraints=List[Constraint](
#             Constraint(-55, 70, "cabin_temp_C"),
#             Constraint(75, 101, "cabin_pressure_kPa"),
#         )
#     )
#     var result = checker.check(60)
#     print(result.severity, result.error_mask)

from memory.unsafe import DTypePointer
from memory import UnsafePointer

alias INT8_MIN: Int8 = -127
alias INT8_MAX: Int8 = 127


@value
struct Severity(Stringable):
    """Constraint violation severity levels."""
    var value: UInt8

    fn __init__(inout self, value: UInt8 = 0):
        self.value = value

    @staticmethod
    fn PASS() -> Severity:
        return Severity(0)

    @staticmethod
    fn CAUTION() -> Severity:
        return Severity(1)

    @staticmethod
    fn WARNING() -> Severity:
        return Severity(2)

    @staticmethod
    fn CRITICAL() -> Severity:
        return Severity(3)

    fn __str__(self) -> String:
        if self.value == 0:
            return "PASS"
        elif self.value == 1:
            return "CAUTION"
        elif self.value == 2:
            return "WARNING"
        else:
            return "CRITICAL"


@value
struct Constraint(Stringable):
    """A single constraint definition with saturated INT8 bounds."""
    var lo: Int8
    var hi: Int8
    var name: String

    fn __init__(inout self, lo: Int, hi: Int, name: String = "C"):
        self.lo = saturate_i8(lo)
        self.hi = saturate_i8(hi)
        self.name = name

    fn __str__(self) -> String:
        return self.name + " [" + str(self.lo) + ", " + str(self.hi) + "]"


@value
struct FluxResult(Stringable):
    """Result of a constraint check."""
    var error_mask: UInt8
    var severity: Severity
    var violated_lo: UInt8
    var violated_hi: UInt8
    var violated_count: UInt8
    var passed: Bool

    fn __init__(inout self):
        self.error_mask = 0
        self.severity = Severity.PASS()
        self.violated_lo = 0
        self.violated_hi = 0
        self.violated_count = 0
        self.passed = True

    fn __str__(self) -> String:
        var base = "sev=" + str(self.severity)
        base += " mask=0x" + str(self.error_mask)
        base += " passed=" + str(self.passed)
        return base


fn saturate_i8(val: Int) -> Int8:
    """Clamp to saturated INT8 [-127, 127]."""
    if val < -127:
        return Int8(-127)
    elif val > 127:
        return Int8(127)
    else:
        return Int8(val)


struct FluxChecker:
    """FLUX INT8 saturated constraint checker. Up to 8 constraints per sensor."""

    var constraints: DynamicVector[Constraint]
    var count: Int

    fn __init__(inout self, constraints: DynamicVector[Constraint]):
        self.count = len(constraints)
        assert(self.count > 0, "FluxConstraint requires non-empty constraints list")
        assert(self.count <= 8, "Maximum 8 constraints (INT8 x8 flat bounds)")
        self.constraints = constraints

    fn check(inout self, value: Int) -> FluxResult:
        """Check a single value against all constraints."""
        let val = saturate_i8(value)
        var result = FluxResult()
        var violated: Int = 0

        for i in range(self.count):
            let c = self.constraints[i]
            let lo_fail = val < c.lo
            let hi_fail = val > c.hi
            let passed = not lo_fail and not hi_fail

            if not passed:
                result.error_mask = result.error_mask | UInt8(1 << i)
                violated += 1
            if lo_fail:
                result.violated_lo = result.violated_lo | UInt8(1 << i)
            if hi_fail:
                result.violated_hi = result.violated_hi | UInt8(1 << i)

        # Severity classification
        if violated == 0:
            result.severity = Severity.PASS()
        elif violated <= self.count // 4:
            result.severity = Severity.CAUTION()
        elif violated <= self.count // 2:
            result.severity = Severity.WARNING()
        else:
            result.severity = Severity.CRITICAL()
        result.violated_count = UInt8(violated)
        result.passed = (violated == 0)

        return result


# Industry presets
fn aviation_preset() -> DynamicVector[Constraint]:
    var v = DynamicVector[Constraint]()
    v.append(Constraint(-55, 70, "cabin_temp_C"))
    v.append(Constraint(75, 101, "cabin_pressure_kPa"))
    v.append(Constraint(0, 100, "fuel_flow_pct"))
    v.append(Constraint(60, 100, "hydraulic_pct"))
    return v

fn automotive_preset() -> DynamicVector[Constraint]:
    var v = DynamicVector[Constraint]()
    v.append(Constraint(-40, 60, "battery_temp_C"))
    v.append(Constraint(0, 100, "soc_pct"))
    v.append(Constraint(0, 100, "charge_rate_pct"))
    v.append(Constraint(20, 80, "cabin_temp_C"))
    return v

fn medical_preset() -> DynamicVector[Constraint]:
    var v = DynamicVector[Constraint]()
    v.append(Constraint(36, 38, "body_temp_C"))
    v.append(Constraint(60, 100, "heart_rate_bpm"))
    v.append(Constraint(95, 100, "spo2_pct"))
    v.append(Constraint(80, 120, "bp_systolic_mmHg"))
    return v


fn main():
    print("╔══════════════════════════════════════════════╗")
    print("║  FLUX Constraint Engine — Mojo               ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    var constraints = aviation_preset()
    var checker = FluxChecker(constraints)

    print("Aviation preset loaded:")
    for i in range(len(checker.constraints)):
        print("  ", checker.constraints[i])

    print("\nExamples:")
    let test_vals = [-60, 0, 25, 70, 90, 127]
    for val in test_vals:
        let result = checker.check(val)
        if result.passed:
            print("  val=", val, ": ✓ mask=0x", result.error_mask)
        else:
            print("  val=", val, ": ✗ ", result)
