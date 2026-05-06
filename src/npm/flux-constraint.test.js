const { FluxConstraint, Severity, saturate } = require('./flux-constraint');

let passed = 0, failed = 0;
function assert(cond, msg) { if (cond) { passed++; } else { failed++; console.error(`FAIL: ${msg}`); } }

// Saturate
assert(saturate(-128) === -127, 'saturate(-128)');
assert(saturate(128) === 127, 'saturate(128)');
assert(saturate(0) === 0, 'saturate(0)');

// Pass
const fc = new FluxConstraint([{lo: 0, hi: 100, name: 'test'}]);
assert(fc.check(50).passed, 'pass');
assert(!fc.check(150).passed, 'fail');

// Severity
const fc2 = new FluxConstraint([
  {lo: 0, hi: 10, name: 'a'}, {lo: 0, hi: 10, name: 'b'},
  {lo: 0, hi: 10, name: 'c'}, {lo: 0, hi: 10, name: 'd'}
]);
assert(fc2.check(50).severity === Severity.CRITICAL, 'critical');

// Preset
const fc3 = FluxConstraint.fromPreset('aviation');
assert(fc3.check(25).details.length === 4, 'aviation 4 constraints');

// Batch
const {results, stats} = fc.checkBatch([-60, 0, 50, 100, 127]);
assert(results.length === 5, 'batch 5');

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
