#!/usr/bin/env bash
# Cross-Language Differential Test Runner
# Runs all available language test runners against golden vectors
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0
SKIP=0
RESULTS=()

run_test() {
    local name="$1"
    local cmd="$2"
    local check_cmd="$3"
    
    if ! eval "$check_cmd" &>/dev/null; then
        RESULTS+=("$name: SKIP (not installed)")
        ((SKIP++))
        return
    fi
    
    echo -n "  Testing $name... "
    if eval "$cmd" 2>/dev/null | tail -1 | grep -q "0 mismatches"; then
        RESULTS+=("$name: ✓ PASS (10,000 vectors, 0 mismatches)")
        ((PASS++))
        echo "✓"
    else
        local output=$(eval "$cmd" 2>&1 | tail -1)
        RESULTS+=("$name: ✗ FAIL ($output)")
        ((FAIL++))
        echo "✗ ($output)"
    fi
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Cross-Language Differential Test — 10,000 Golden Vectors   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Ensure golden vectors exist
if [ ! -f tools/golden_vectors.json ]; then
    echo "  Generating golden vectors..."
    python3 tools/generate_golden_vectors.py > tools/golden_vectors.json
fi

echo "  Vectors: $(python3 -c "import json; print(len(json.load(open('tools/golden_vectors.json'))))")"
echo ""

# Python
run_test "Python" "python3 tools/test_golden.py" "which python3"

# JavaScript
run_test "JavaScript" "node tools/test_golden.js" "which node"

# TypeScript (via npx tsx)
run_test "TypeScript" "npx tsx tools/test_golden.ts" "which npx"

# Go (standalone, uses go:build ignore so we run directly)
run_test "Go" "go run tools/test_golden.go" "which go"

# Ruby
run_test "Ruby" "ruby tools/test_golden.rb" "which ruby"

# PHP
run_test "PHP" "php tools/test_golden.php" "which php"

# Dart
run_test "Dart" "dart run tools/test_golden.dart" "which dart"

# Zig
run_test "Zig" "zig run tools/test_golden.zig" "which zig"

# Kotlin (script)
run_test "Kotlin" "kotlinc -script tools/test_golden.kts" "which kotlinc"

# Java (needs compilation)
run_test "Java" "cd src/java && javac FluxConstraint.java && cd ../.. && java -cp src/java FluxConstraint" "which javac"

# C# (via dotnet-script or csx)
run_test "C#" "dotnet script tools/test_golden.csx" "which dotnet"

# Swift
run_test "Swift" "swift tools/test_golden.swift" "which swift"

# Elixir
run_test "Elixir" "cd tools && elixir test_golden.exs && cd .." "which elixir"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Results Summary                                            ║"
echo "╠══════════════════════════════════════════════════════════════╣"
for r in "${RESULTS[@]}"; do
    printf "  %-55s ║\n" "$r"
done
echo "╠══════════════════════════════════════════════════════════════╣"
printf "  Pass: %-3d  Fail: %-3d  Skip: %-3d                      ║\n" "$PASS" "$FAIL" "$SKIP"
echo "╚══════════════════════════════════════════════════════════════╝"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
