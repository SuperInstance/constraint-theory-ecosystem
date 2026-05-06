package flux

/**
 * FLUX Constraint Engine — Scala 3
 * Pure INT8 saturated constraint checking. Zero dependencies.
 *
 * Usage:
 *   val checker = FluxChecker(Seq(Constraint(0, 100, "temp")))
 *   val result = checker.check(70)
 *   println(result.severity) // Caution
 */

object FluxConstraint:

  val INT8_MIN: Int = -127
  val INT8_MAX: Int = 127

  def saturate(val0: Int): Int =
    math.max(INT8_MIN, math.min(INT8_MAX, val0))

  enum Severity(val code: Int):
    case Pass     extends Severity(0)
    case Caution  extends Severity(1)
    case Warning  extends Severity(2)
    case Critical extends Severity(3)

  case class Constraint(lo: Int, hi: Int, name: String):
    lazy val satLo: Int = saturate(lo)
    lazy val satHi: Int = saturate(hi)

  case class FluxResult(
    errorMask: Int = 0,
    severity: Severity = Severity.Pass,
    violatedLo: Int = 0,
    violatedHi: Int = 0,
    violatedCount: Int = 0,
    passed: Boolean = true
  )

  // Industry presets
  val presets: Map[String, Seq[Constraint]] = Map(
    "aviation" -> Seq(
      Constraint(-55, 70, "cabin_temp_C"),
      Constraint(75, 101, "cabin_pressure_kPa"),
      Constraint(0, 100, "fuel_flow_pct"),
      Constraint(60, 100, "hydraulic_pct")
    ),
    "medical" -> Seq(
      Constraint(36, 38, "body_temp_C"),
      Constraint(60, 100, "heart_rate_bpm"),
      Constraint(95, 100, "spo2_pct"),
      Constraint(80, 120, "bp_systolic_mmHg")
    ),
    "maritime" -> Seq(
      Constraint(-2, 35, "sea_temp_C"),
      Constraint(50, 100, "hull_integrity_pct"),
      Constraint(0, 50, "wave_height_m"),
      Constraint(0, 80, "wind_speed_kn")
    ),
    "automotive" -> Seq(
      Constraint(-40, 60, "battery_temp_C"),
      Constraint(0, 100, "soc_pct"),
      Constraint(0, 100, "charge_rate_pct"),
      Constraint(20, 80, "cabin_temp_C")
    ),
    "energy" -> Seq(
      Constraint(49, 51, "grid_freq_Hz_x10"),
      Constraint(95, 105, "voltage_pct"),
      Constraint(0, 80, "transformer_temp_C"),
      Constraint(0, 100, "line_load_pct")
    )
  )

  def availablePresets: Seq[String] = presets.keys.toSeq

class FluxChecker(val constraints: Seq[FluxConstraint.Constraint]):
  require(constraints.nonEmpty, "FluxChecker requires non-empty constraints")
  require(constraints.length <= 8, "Maximum 8 constraints (INT8 × 8 flat bounds)")

  import FluxConstraint.*

  def check(value: Int): FluxResult =
    val val0 = saturate(value)
    var errorMask = 0
    var violatedLo = 0
    var violatedHi = 0
    var violatedCount = 0

    for i <- constraints.indices do
      val c = constraints(i)
      val loFail = val0 < c.satLo
      val hiFail = val0 > c.satHi
      if loFail || hiFail then
        errorMask |= (1 << i)
        violatedCount += 1
      if loFail then violatedLo |= (1 << i)
      if hiFail then violatedHi |= (1 << i)

    val nc = constraints.length
    val sev = if violatedCount == 0 then Severity.Pass
              else if violatedCount <= nc / 4 then Severity.Caution
              else if violatedCount <= nc / 2 then Severity.Warning
              else Severity.Critical

    FluxResult(errorMask, sev, violatedLo, violatedHi, violatedCount, sev == Severity.Pass)

  def checkBatch(values: Seq[Int]): (Seq[FluxResult], Map[String, Int]) =
    val results = values.map(check)
    val stats = Map(
      "pass" -> results.count(_.severity == Severity.Pass),
      "caution" -> results.count(_.severity == Severity.Caution),
      "warning" -> results.count(_.severity == Severity.Warning),
      "critical" -> results.count(_.severity == Severity.Critical)
    )
    (results, stats)

  def benchmark(iterations: Int = 1000000): (Double, Double) =
    val t0 = System.nanoTime()
    for i <- 0 until iterations do
      check((i % 254) - 127)
    val t1 = System.nanoTime()
    val elapsedMs = (t1 - t0) / 1e6
    val rate = iterations * constraints.length / (elapsedMs / 1000.0)
    (rate, elapsedMs)

object FluxChecker:
  import FluxConstraint.*

  def apply(constraints: Seq[Constraint]): FluxChecker =
    new FluxChecker(constraints)

  def fromPreset(name: String): Either[String, FluxChecker] =
    presets.get(name) match
      case Some(cs) => Right(new FluxChecker(cs))
      case None => Left(s"Unknown preset: $name. Available: ${availablePresets.mkString(", ")}")

  // Tests (run with scala-cli or scalac)
  def main(args: Array[String]): Unit =
    println("╔══════════════════════════════════════════════════════╗")
    println("║  FLUX Constraint Engine — Scala                      ║")
    println("╚══════════════════════════════════════════════════════╝\n")

    // Test 1: saturate
    assert(saturate(-128) == -127, "saturate(-128)")
    assert(saturate(128) == 127, "saturate(128)")
    assert(saturate(0) == 0, "saturate(0)")
    println("✓ saturate boundaries")

    // Test 2: pass
    val fc = FluxChecker(Seq(Constraint(0, 100, "test")))
    val r1 = fc.check(50)
    assert(r1.passed, "should pass")
    println("✓ single constraint pass")

    // Test 3: fail
    val r2 = fc.check(150)
    assert(!r2.passed, "should fail")
    assert(r2.errorMask != 0, "should have error")
    println("✓ single constraint fail")

    // Test 4: multi constraint
    val fc2 = FluxChecker(Seq(
      Constraint(0, 50, "a"),
      Constraint(0, 100, "b"),
      Constraint(-10, 10, "c")
    ))
    val r3 = fc2.check(30)
    assert(!r3.passed, "should fail")
    println("✓ multi constraint mixed")

    // Test 5: critical severity
    val fc3 = FluxChecker(Seq(
      Constraint(0, 10, "a"),
      Constraint(0, 10, "b"),
      Constraint(0, 10, "c"),
      Constraint(0, 10, "d")
    ))
    val r4 = fc3.check(50)
    assert(r4.severity == Severity.Critical, "should be critical")
    assert(r4.violatedCount == 4, "all 4 should fail")
    println("✓ severity critical")

    // Test 6: preset loading
    val Right(fc4) = FluxChecker.fromPreset("aviation")
    assert(fc4.constraints.length == 4, "aviation should have 4")
    println("✓ preset loading")

    // Test 7: batch
    val (results, stats) = fc.checkBatch(Seq(-60, 0, 50, 100, 127))
    assert(results.length == 5, "should have 5 results")
    println("✓ batch checking")

    // Benchmark
    val (rate, ms) = fc4.benchmark()
    println(f"\n  Benchmark: ${rate / 1e6}%.1fM checks/sec (${ms}%.1fms)")
    println(s"\n  Available presets: ${availablePresets.mkString(", ")}")
    println("\n  ✓ All tests pass")
