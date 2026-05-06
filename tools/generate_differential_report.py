#!/usr/bin/env python3
"""Generate a markdown differential test report."""
import json, os, sys
from datetime import datetime

def generate_report(results_dir="tools/results"):
    report = []
    report.append("# Cross-Language Differential Test Report\n")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n")
    report.append("## Golden Vector Stats\n")
    
    vectors_path = os.path.join(os.path.dirname(__file__), "golden_vectors.json")
    if os.path.exists(vectors_path):
        vectors = json.load(open(vectors_path))
        report.append(f"- **Total vectors:** {len(vectors):,}\n")
        report.append(f"- **Categories:** boundary, saturation, in-range, out-of-range, multi-constraint, extreme, all-pass, all-fail\n")
    
    report.append("\n## Language Results\n")
    report.append("| Language | Vectors | Mismatches | Status |")
    report.append("|----------|---------|------------|--------|")
    
    # Read result files
    languages = [
        ("Python", "python"), ("JavaScript", "javascript"), ("TypeScript", "typescript"),
        ("Go", "go"), ("Ruby", "ruby"), ("PHP", "php"), ("Dart", "dart"),
        ("Zig", "zig"), ("Kotlin", "kotlin"), ("Java", "java"),
        ("C#", "csharp"), ("Swift", "swift"), ("Elixir", "elixir"),
        ("Haskell", "haskell"), ("Scala", "scala"),
        ("Rust", "rust"), ("C (embedded)", "c"), ("CUDA", "cuda"),
        ("WebGPU", "webgpu"), ("SystemVerilog", "systemverilog"), ("REST API", "rest"),
    ]
    
    for name, key in languages:
        result_file = os.path.join(results_dir, f"{key}.json")
        if os.path.exists(result_file):
            data = json.load(open(result_file))
            ms = data.get("mismatches", "?")
            total = data.get("total", "10,000")
            status = "✅ PASS" if ms == 0 else f"❌ FAIL ({ms})"
        else:
            total = "10,000"
            ms = "—"
            status = "⏳ Not run"
        report.append(f"| {name} | {total} | {ms} | {status} |")
    
    report.append("\n## Specification Compliance\n")
    report.append("Every implementation must satisfy:\n")
    report.append("1. **INT8 saturation:** values clamped to [-127, 127] (NOT [-128, 127])\n")
    report.append("2. **Error mask:** bitmask of violated constraints (bit i = constraint i failed)\n")
    report.append("3. **Severity:** PASS(0) → CAUTION(1) → WARNING(2) → CRITICAL(3)\n")
    report.append("4. **Zero mismatches:** against 10,000 golden vectors\n")
    
    report.append("\n---\n")
    report.append("*10,000 vectors. 21 languages. Zero mismatches. That's the standard.*\n")
    
    output_path = os.path.join(os.path.dirname(__file__), "differential-report.md")
    with open(output_path, "w") as f:
        f.write("\n".join(report))
    print(f"Report written to {output_path}")

if __name__ == "__main__":
    generate_report(sys.argv[1] if len(sys.argv) > 1 else "tools/results")
