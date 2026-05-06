// FLUX Constraint Engine — Dart
// Pure INT8 saturated constraint checking. Zero dependencies.

const int int8Min = -127;
const int int8Max = 127;

int saturate(int val) => val < int8Min ? int8Min : (val > int8Max ? int8Max : val);

enum Severity { pass, caution, warning, critical }

class Constraint {
  final int lo, hi;
  final String name;
  Constraint(this.lo, this.hi, this.name);
}

class FluxResult {
  final int errorMask;
  final Severity severity;
  final int violatedLo;
  final int violatedHi;
  final int violatedCount;
  final bool passed;
  FluxResult({
    this.errorMask = 0,
    this.severity = Severity.pass,
    this.violatedLo = 0,
    this.violatedHi = 0,
    this.violatedCount = 0,
    this.passed = true,
  });
}

class FluxChecker {
  final List<Constraint> constraints;

  FluxChecker(this.constraints) {
    if (constraints.isEmpty) throw ArgumentError('Non-empty constraints required');
    if (constraints.length > 8) throw ArgumentError('Max 8 constraints');
  }

  FluxResult check(int value) {
    final val = saturate(value);
    int errorMask = 0, violatedLo = 0, violatedHi = 0, violatedCount = 0;

    for (var i = 0; i < constraints.length; i++) {
      final c = constraints[i];
      final lo = saturate(c.lo), hi = saturate(c.hi);
      final loFail = val < lo, hiFail = val > hi;
      if (loFail || hiFail) { errorMask |= (1 << i); violatedCount++; }
      if (loFail) violatedLo |= (1 << i);
      if (hiFail) violatedHi |= (1 << i);
    }

    final nc = constraints.length;
    final sev = violatedCount == 0 ? Severity.pass
        : violatedCount <= nc ~/ 4 ? Severity.caution
        : violatedCount <= nc ~/ 2 ? Severity.warning
        : Severity.critical;

    return FluxResult(
      errorMask: errorMask,
      severity: sev,
      violatedLo: violatedLo,
      violatedHi: violatedHi,
      violatedCount: violatedCount,
      passed: sev == Severity.pass,
    );
  }

  List<FluxResult> checkBatch(List<int> values) => values.map(check).toList();

  (double, double) benchmark([int iterations = 1000000]) {
    final sw = Stopwatch()..start();
    for (var i = 0; i < iterations; i++) check((i % 254) - 127);
    sw.stop();
    final rate = iterations * constraints.length / (sw.elapsedMilliseconds / 1000.0);
    return (rate, sw.elapsedMilliseconds.toDouble());
  }

  static FluxChecker fromPreset(String name) {
    final cs = presets[name];
    if (cs == null) throw ArgumentError('Unknown preset: $name');
    return FluxChecker(cs);
  }

  static final Map<String, List<Constraint>> presets = {
    'aviation': [
      Constraint(-55, 70, 'cabin_temp_C'),
      Constraint(75, 101, 'cabin_pressure_kPa'),
      Constraint(0, 100, 'fuel_flow_pct'),
      Constraint(60, 100, 'hydraulic_pct'),
    ],
    'medical': [
      Constraint(36, 38, 'body_temp_C'),
      Constraint(60, 100, 'heart_rate_bpm'),
      Constraint(95, 100, 'spo2_pct'),
      Constraint(80, 120, 'bp_systolic_mmHg'),
    ],
    'maritime': [
      Constraint(-2, 35, 'sea_temp_C'),
      Constraint(50, 100, 'hull_integrity_pct'),
      Constraint(0, 50, 'wave_height_m'),
      Constraint(0, 80, 'wind_speed_kn'),
    ],
    'automotive': [
      Constraint(-40, 60, 'battery_temp_C'),
      Constraint(0, 100, 'soc_pct'),
      Constraint(0, 100, 'charge_rate_pct'),
      Constraint(20, 80, 'cabin_temp_C'),
    ],
    'energy': [
      Constraint(49, 51, 'grid_freq_Hz_x10'),
      Constraint(95, 105, 'voltage_pct'),
      Constraint(0, 80, 'transformer_temp_C'),
      Constraint(0, 100, 'line_load_pct'),
    ],
  };
}

void main() {
  print('╔══════════════════════════════════════════════════════╗');
  print('║  FLUX Constraint Engine — Dart                       ║');
  print('╚══════════════════════════════════════════════════════╝\n');

  assert(saturate(-128) == -127); assert(saturate(128) == 127); assert(saturate(0) == 0);
  print('✓ saturate boundaries');

  final fc = FluxChecker([Constraint(0, 100, 'test')]);
  assert(fc.check(50).passed); print('✓ single pass');
  assert(!fc.check(150).passed); print('✓ single fail');

  final fc2 = FluxChecker([Constraint(0,10,'a'), Constraint(0,10,'b'),
                            Constraint(0,10,'c'), Constraint(0,10,'d')]);
  final r = fc2.check(50);
  assert(r.severity == Severity.critical); assert(r.violatedCount == 4);
  print('✓ severity critical');

  final fc3 = FluxChecker.fromPreset('aviation');
  assert(fc3.constraints.length == 4); print('✓ preset loading');

  final results = fc.checkBatch([-60, 0, 50, 100, 127]);
  assert(results.length == 5); print('✓ batch checking');

  final (rate, ms) = fc3.benchmark();
  print('\n  Benchmark: ${(rate / 1e6).toStringAsFixed(1)}M checks/sec (${ms.toStringAsFixed(1)}ms)');
  print('\n  ✓ All tests pass');
}
