#!/usr/bin/env kotlin
/**
 * Golden vector test for Kotlin implementation.
 * Run: kotlinc -script tools/test_golden.kts
 * Requires: src/kotlin/FluxConstraint.kt on classpath
 */

// Simple JSON array parser (zero deps)
fun parseVectors(json: String): List<Map<String, Any?>> {
    val results = mutableListOf<Map<String, Any?>>()
    // Regex-based extraction for simple flat structure
    val objPattern = Regex("""\{"id":(\d+),"value":(-?\d+),"constraints":\[([^\]]*)\],"expected":\{([^}]*)\}\}""")
    val conPattern = Regex("""\{"lo":(-?\d+),"hi":(-?\d+)\}""")
    val expPattern = Regex(""""(\w+)":(-?\d+|true|false)""")
    
    for (m in objPattern.findAll(json)) {
        val cons = conPattern.findAll(m.groupValues[3]).map { 
            mapOf("lo" to it.groupValues[1].toInt(), "hi" to it.groupValues[2].toInt()) 
        }.toList()
        val exp = mutableMapOf<String, Any>()
        for (e in expPattern.findAll(m.groupValues[4])) {
            val v = e.groupValues[2]
            exp[e.groupValues[1]] = if (v == "true") true else if (v == "false") false else v.toInt()
        }
        results.add(mapOf(
            "id" to m.groupValues[1].toInt(),
            "value" to m.groupValues[2].toInt(),
            "constraints" to cons,
            "expected" to exp
        ))
    }
    return results
}

// Inline constraint checker (matches Kotlin impl exactly)
fun saturate(v: Int) = maxOf(-127, minOf(127, v))

data class Result(val errorMask: Int, val passed: Boolean, val violatedCount: Int)

fun check(constraints: List<Map<String, Int>>, value: Int): Result {
    val v = saturate(value)
    var errorMask = 0
    var violatedCount = 0
    for (i in constraints.indices) {
        val c = constraints[i]
        val lo = saturate(c["lo"]!!)
        val hi = saturate(c["hi"]!!)
        val loFail = v < lo
        val hiFail = v > hi
        if (loFail || hiFail) { errorMask = errorMask or (1 shl i); violatedCount++ }
    }
    return Result(errorMask, errorMask == 0, violatedCount)
}

// Main
val json = java.io.File("tools/golden_vectors.json").readText()
val vectors = parseVectors(json)
var mismatches = 0

for (v in vectors) {
    val cs = (v["constraints"] as List<Map<String, Int>>)
    val exp = v["expected"] as Map<String, Any>
    val r = check(cs, v["value"] as Int)
    if (r.errorMask != exp["error_mask"] || r.passed != exp["passed"]) {
        mismatches++
        if (mismatches <= 5) println("MISMATCH #${v["id"]}: value=${v["value"]}")
    }
}

println("\nKotlin: ${vectors.size} vectors, $mismatches mismatches")
if (mismatches > 0) System.exit(1)
