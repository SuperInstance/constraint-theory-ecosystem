#!/usr/bin/env python3
"""Test Python implementation against golden vectors."""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))
from flux_constraint import FluxConstraint

vectors = json.load(open(os.path.join(os.path.dirname(__file__), 'golden_vectors.json')))
mismatches = 0

for v in vectors:
    cs = [{"lo": c["lo"], "hi": c["hi"], "name": ""} for c in v["constraints"]]
    fc = FluxConstraint(cs)
    r = fc.check(v["value"])
    exp = v["expected"]
    if r.error_mask != exp["error_mask"] or r.passed != exp["passed"] or r.violated_count != exp["violated_count"]:
        mismatches += 1
        if mismatches <= 5:
            print(f"MISMATCH #{v['id']}: value={v['value']} got mask={r.error_mask} passed={r.passed} exp mask={exp['error_mask']} passed={exp['passed']}")

print(f"\nPython: {len(vectors)} vectors, {mismatches} mismatches", flush=True)
sys.exit(1 if mismatches > 0 else 0)
