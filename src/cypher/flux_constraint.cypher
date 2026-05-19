// FLUX Constraint Engine — Cypher (2009, Graph Query Language)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: Cypher is Neo4j's graph query language. Constraints are
// GRAPH PATTERNS. A constraint violation is a FAILED MATCH — the graph
// doesn't contain a valid path from value to acceptable range.
// The graph IS the constraint system. Relationships ARE the bounds.
//
// "Constraints as graph patterns. A violation is a missing edge.
//  The query IS the check. The graph IS the constraint system."

// ══ Schema: Create the constraint graph ═══════════════════════════
// Nodes: Sensor, Constraint, Severity, Result
// Relationships: HAS_CONSTRAINT, CHECKED_BY, VIOLATES, SATISFIES

// Create constraint nodes with bounds
CREATE (c1:Constraint {name: "cabin_temp_C", lo: -55, hi: 70, preset: "aviation"})
CREATE (c2:Constraint {name: "cabin_pressure_kPa", lo: 75, hi: 101, preset: "aviation"})
CREATE (c3:Constraint {name: "fuel_flow_pct", lo: 0, hi: 100, preset: "aviation"})
CREATE (c4:Constraint {name: "hydraulic_pct", lo: 60, hi: 100, preset: "aviation"})

CREATE (c5:Constraint {name: "battery_temp_C", lo: -40, hi: 60, preset: "automotive"})
CREATE (c6:Constraint {name: "soc_pct", lo: 0, hi: 100, preset: "automotive"})
CREATE (c7:Constraint {name: "charge_rate_pct", lo: 0, hi: 100, preset: "automotive"})
CREATE (c8:Constraint {name: "cabin_temp_C", lo: 20, hi: 80, preset: "automotive"})

CREATE (c9:Constraint {name: "body_temp_C", lo: 36, hi: 38, preset: "medical"})
CREATE (c10:Constraint {name: "heart_rate_bpm", lo: 60, hi: 100, preset: "medical"})
CREATE (c11:Constraint {name: "spo2_pct", lo: 95, hi: 100, preset: "medical"})
CREATE (c12:Constraint {name: "bp_systolic_mmHg", lo: 80, hi: 120, preset: "medical"})

CREATE (c13:Constraint {name: "neutron_flux_pct", lo: 0, hi: 110, preset: "nuclear"})
CREATE (c14:Constraint {name: "core_temp_C_x10", lo: 0, hi: 65, preset: "nuclear"})
CREATE (c15:Constraint {name: "pressurizer_pct", lo: 72, hi: 100, preset: "nuclear"})
CREATE (c16:Constraint {name: "coolant_flow_pct", lo: 0, hi: 100, preset: "nuclear"})

// ══ Saturate: Cypher CASE expression ═════════════════════════════

// Saturate a value to INT8 range
// This is a pure Cypher expression:
// CASE WHEN val < -127 THEN -127
//      WHEN val > 127 THEN 127
//      ELSE val END

// ══ Core Check: Single constraint check ═══════════════════════════
// Check a value against a preset's constraints

// Returns all constraints violated by value=60 for aviation preset
MATCH (c:Constraint {preset: 'aviation'})
WITH c,
     60 AS rawVal,
     CASE WHEN 60 < -127 THEN -127
          WHEN 60 > 127 THEN 127
          ELSE 60 END AS val
WHERE val < c.lo OR val > c.hi
RETURN c.name AS violated_constraint,
       c.lo AS lo, c.hi AS hi,
       val AS value,
       CASE WHEN val < c.lo THEN 'LO_VIOLATION'
            WHEN val > c.hi THEN 'HI_VIOLATION'
       END AS violation_type

// ══ Full Check with Error Mask ═══════════════════════════════════
// Compute error_mask, severity, and all result fields in one query

MATCH (c:Constraint {preset: $preset})
WITH collect(c) AS constraints, $rawVal AS rawVal
WITH constraints,
     CASE WHEN rawVal < -127 THEN -127
          WHEN rawVal > 127 THEN 127
          ELSE rawVal END AS val,
     size(constraints) AS n
UNWIND range(0, size(constraints)-1) AS i
WITH constraints, val, n, i,
     constraints[i] AS c,
     CASE WHEN val < constraints[i].lo THEN true ELSE false END AS loFail,
     CASE WHEN val > constraints[i].hi THEN true ELSE false END AS hiFail
WITH val, n,
     sum(CASE WHEN loFail OR hiFail THEN toInteger(2^i) ELSE 0 END) AS errorMask,
     sum(CASE WHEN loFail THEN toInteger(2^i) ELSE 0 END) AS violatedLo,
     sum(CASE WHEN hiFail THEN toInteger(2^i) ELSE 0 END) AS violatedHi,
     sum(CASE WHEN loFail OR hiFail THEN 1 ELSE 0 END) AS violatedCount
RETURN val,
       errorMask,
       violatedLo,
       violatedHi,
       violatedCount,
       CASE
         WHEN violatedCount = 0 THEN 'PASS'
         WHEN violatedCount <= n / 4 THEN 'CAUTION'
         WHEN violatedCount <= n / 2 THEN 'WARNING'
         ELSE 'CRITICAL'
       END AS severity,
       violatedCount = 0 AS passed

// ══ Batch Check: Multiple values ═════════════════════════════════
// Check each value in a list against a preset

UNWIND $values AS rawVal
MATCH (c:Constraint {preset: $preset})
WITH rawVal, collect(c) AS constraints,
     CASE WHEN rawVal < -127 THEN -127
          WHEN rawVal > 127 THEN 127
          ELSE rawVal END AS val,
     count(c) AS n
UNWIND range(0, size(constraints)-1) AS i
WITH rawVal, val, n, i, constraints[i] AS c,
     CASE WHEN val < constraints[i].lo THEN true ELSE false END AS loFail,
     CASE WHEN val > constraints[i].hi THEN true ELSE false END AS hiFail
WITH rawVal, val, n,
     sum(CASE WHEN loFail OR hiFail THEN toInteger(2^i) ELSE 0 END) AS errorMask,
     sum(CASE WHEN loFail OR hiFail THEN 1 ELSE 0 END) AS violatedCount
RETURN rawVal, val, errorMask, violatedCount,
       CASE
         WHEN violatedCount = 0 THEN 'PASS'
         WHEN violatedCount <= n / 4 THEN 'CAUTION'
         WHEN violatedCount <= n / 2 THEN 'WARNING'
         ELSE 'CRITICAL'
       END AS severity,
       violatedCount = 0 AS passed
ORDER BY rawVal

// ══ Constraint Graph Analysis ════════════════════════════════════
// Find overlapping constraints across presets (unique to graph approach)

MATCH (c1:Constraint), (c2:Constraint)
WHERE c1.preset <> c2.preset
  AND c1.name = c2.name
  AND c1.hi >= c2.lo AND c2.hi >= c1.lo
RETURN c1.preset AS preset1, c2.preset AS preset2,
       c1.name AS constraint_name,
       max(c1.lo, c2.lo) AS overlap_lo,
       min(c1.hi, c2.hi) AS overlap_hi

// ══ Find contradictions ═══════════════════════════════════════════
// Constraints where lo > hi (should never happen)

MATCH (c:Constraint)
WHERE c.lo > c.hi
RETURN c.name, c.preset, c.lo, c.hi
// Should return 0 rows — all constraints are valid

// Cypher teaches us that constraints are GRAPH PATTERNS.
// A violation is a failed match — the graph doesn't contain
// a path from the value to the acceptable range.
// Relationships ARE the bounds. Nodes ARE the values.
// The graph IS the constraint system.
// For complex interdependencies, graph queries find contradictions
// and overlaps that scalar checking misses.
