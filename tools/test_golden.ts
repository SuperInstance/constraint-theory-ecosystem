import * as fs from 'fs';
import * as path from 'path';
import { FluxConstraint, Severity } from '../src/typescript/flux-constraint';

const vectors = JSON.parse(fs.readFileSync(path.join(__dirname, 'golden_vectors.json'), 'utf-8'));
let mismatches = 0;

for (const v of vectors) {
    const cs = v.constraints.map((c: any) => ({ lo: c.lo, hi: c.hi, name: '' }));
    const fc = new FluxConstraint(cs);
    const r = fc.check(v.value);
    const exp = v.expected;
    if (r.errorMask !== exp.error_mask || r.passed !== exp.passed || r.violatedCount !== exp.violated_count) {
        mismatches++;
        if (mismatches <= 5) console.log(`MISMATCH #${v.id}: value=${v.value} got mask=${r.errorMask} passed=${r.passed} expected mask=${exp.error_mask}`);
    }
}

console.log(`\nTypeScript: ${vectors.length} vectors, ${mismatches} mismatches`);
process.exit(mismatches > 0 ? 1 : 0);
