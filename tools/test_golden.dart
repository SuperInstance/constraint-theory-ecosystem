import 'dart:io';
import 'dart:convert';
import '../src/dart/flux_constraint.dart';

void main() {
  final vectors = jsonDecode(File('tools/golden_vectors.json').readAsStringSync()) as List;
  int mismatches = 0;

  for (final v in vectors) {
    final cs = (v['constraints'] as List).map((c) => Constraint(c['lo'], c['hi'], '')).toList();
    final fc = FluxChecker(cs);
    final r = fc.check(v['value']);
    final exp = v['expected'];
    if (r.errorMask != exp['error_mask'] || r.passed != exp['passed'] || r.violatedCount != exp['violated_count']) {
      mismatches++;
      if (mismatches <= 5) print('MISMATCH #${v["id"]}: value=${v["value"]} got mask=${r.errorMask}');
    }
  }

  print('\nDart: ${vectors.length} vectors, $mismatches mismatches');
  exit(mismatches > 0 ? 1 : 0);
}
