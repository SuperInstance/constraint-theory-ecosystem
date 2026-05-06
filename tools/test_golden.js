#!/usr/bin/env node
/** Test JavaScript implementation against golden vectors. */
const fs = require('fs');
const path = require('path');
const {FluxConstraint} = require(path.join(__dirname, '..', 'src', 'js', 'flux-constraint'));

const vectors = JSON.parse(fs.readFileSync(path.join(__dirname, 'golden_vectors.json')));
let mismatches = 0;

for (const v of vectors) {
    const fc = new FluxConstraint(v.constraints.map(c => ({lo: c.lo, hi: c.hi, name: ''})));
    const r = fc.check(v.value);
    const exp = v.expected;
    if (r.errorMask !== exp.error_mask || r.passed !== exp.passed || r.violatedCount !== exp.violated_count) {
        mismatches++;
        if (mismatches <= 5) console.log(`MISMATCH #${v.id}: value=${v.value} got mask=${r.errorMask} passed=${r.passed}`);
    }
}

console.log(`\nJavaScript: ${vectors.length} vectors, ${mismatches} mismatches`);
process.exit(mismatches > 0 ? 1 : 0);
