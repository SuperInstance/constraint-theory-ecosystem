package flux

/**
 * FLUX Constraint Engine — Kotlin
 * Pure INT8 saturated constraint checking. Zero dependencies.
 */

data class Constraint(val lo: Int, val hi: Int, val name: String) {
    val satLo: Int = maxOf(-127, minOf(127, lo))
    val satHi: Int = maxOf(-127, minOf(127, hi))
}

enum class Severity(val code: Int) {
    PASS(0), CAUTION(1), WARNING(2), CRITICAL(3)
}

data class FluxResult(
    val errorMask: Int,
    val severity: Severity,
    val violatedLo: Int,
    val violatedHi: Int,
    val violatedCount: Int,
    val passed: Boolean
)

class FluxChecker(val constraints: List<Constraint>) {
    init {
        require(constraints.isNotEmpty()) { "Non-empty constraints required" }
        require(constraints.size <= 8) { "Max 8 constraints (INT8 × 8 flat bounds)" }
    }

    fun check(value: Int): FluxResult {
        val v = saturate(value)
        var errorMask = 0
        var violatedLo = 0
        var violatedHi = 0
        var violatedCount = 0

        for (i in constraints.indices) {
            val c = constraints[i]
            val loFail = v < c.satLo
            val hiFail = v > c.satHi
            if (loFail || hiFail) { errorMask = errorMask or (1 shl i); violatedCount++ }
            if (loFail) violatedLo = violatedLo or (1 shl i)
            if (hiFail) violatedHi = violatedHi or (1 shl i)
        }

        val nc = constraints.size
        val sev = when {
            violatedCount == 0 -> Severity.PASS
            violatedCount <= nc / 4 -> Severity.CAUTION
            violatedCount <= nc / 2 -> Severity.WARNING
            else -> Severity.CRITICAL
        }

        return FluxResult(errorMask, sev, violatedLo, violatedHi, violatedCount, sev == Severity.PASS)
    }

    fun checkBatch(values: List<Int>): Pair<List<FluxResult>, Map<String, Int>> {
        val results = values.map { check(it) }
        val stats = mapOf(
            "pass" to results.count { it.severity == Severity.PASS },
            "caution" to results.count { it.severity == Severity.CAUTION },
            "warning" to results.count { it.severity == Severity.WARNING },
            "critical" to results.count { it.severity == Severity.CRITICAL }
        )
        return results to stats
    }

    fun benchmark(iterations: Int = 1_000_000): Pair<Double, Double> {
        val t0 = System.nanoTime()
        repeat(iterations) { check((it % 254) - 127) }
        val t1 = System.nanoTime()
        val ms = (t1 - t0) / 1e6
        val rate = iterations * constraints.size / (ms / 1000.0)
        return rate to ms
    }

    companion object {
        fun saturate(v: Int) = maxOf(-127, minOf(127, v))

        val presets = mapOf(
            "aviation" to listOf(
                Constraint(-55, 70, "cabin_temp_C"),
                Constraint(75, 101, "cabin_pressure_kPa"),
                Constraint(0, 100, "fuel_flow_pct"),
                Constraint(60, 100, "hydraulic_pct")
            ),
            "medical" to listOf(
                Constraint(36, 38, "body_temp_C"),
                Constraint(60, 100, "heart_rate_bpm"),
                Constraint(95, 100, "spo2_pct"),
                Constraint(80, 120, "bp_systolic_mmHg")
            ),
            "maritime" to listOf(
                Constraint(-2, 35, "sea_temp_C"),
                Constraint(50, 100, "hull_integrity_pct"),
                Constraint(0, 50, "wave_height_m"),
                Constraint(0, 80, "wind_speed_kn")
            ),
            "automotive" to listOf(
                Constraint(-40, 60, "battery_temp_C"),
                Constraint(0, 100, "soc_pct"),
                Constraint(0, 100, "charge_rate_pct"),
                Constraint(20, 80, "cabin_temp_C")
            ),
            "energy" to listOf(
                Constraint(49, 51, "grid_freq_Hz_x10"),
                Constraint(95, 105, "voltage_pct"),
                Constraint(0, 80, "transformer_temp_C"),
                Constraint(0, 100, "line_load_pct")
            )
        )

        fun fromPreset(name: String): FluxChecker {
            val cs = presets[name] ?: throw IllegalArgumentException(
                "Unknown preset: $name. Available: ${presets.keys.joinToString(", ")}"
            )
            return FluxChecker(cs)
        }
    }
}

fun main() {
    println("╔══════════════════════════════════════════════════════╗")
    println("║  FLUX Constraint Engine — Kotlin                     ║")
    println("╚══════════════════════════════════════════════════════╝\n")

    // Tests
    assert(FluxChecker.saturate(-128) == -127) { "saturate(-128)" }
    assert(FluxChecker.saturate(128) == 127) { "saturate(128)" }
    println("✓ saturate boundaries")

    val fc = FluxChecker(listOf(Constraint(0, 100, "test")))
    assert(fc.check(50).passed) { "should pass" }
    println("✓ single pass")

    assert(!fc.check(150).passed) { "should fail" }
    println("✓ single fail")

    val fc2 = FluxChecker(listOf(Constraint(0, 10, "a"), Constraint(0, 10, "b"),
                                  Constraint(0, 10, "c"), Constraint(0, 10, "d")))
    val r = fc2.check(50)
    assert(r.severity == Severity.CRITICAL) { "should be critical" }
    assert(r.violatedCount == 4) { "all 4" }
    println("✓ severity critical")

    val fc3 = FluxChecker.fromPreset("aviation")
    assert(fc3.constraints.size == 4) { "aviation has 4" }
    println("✓ preset loading")

    val (results, stats) = fc.checkBatch(listOf(-60, 0, 50, 100, 127))
    assert(results.size == 5) { "5 results" }
    println("✓ batch checking")

    val (rate, ms) = fc3.benchmark()
    println("\n  Benchmark: ${"%.1f".format(rate / 1e6)}M checks/sec (${("%.1f".format(ms))}ms)")
    println("\n  ✓ All tests pass")
}
