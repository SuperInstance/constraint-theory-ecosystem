#!/bin/bash
# FLUX Real-World Benchmark Suite — Runner
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="$RESULTS_DIR/results_${TIMESTAMP}.json"

echo "======================================================================"
echo "FLUX REAL-WORLD BENCHMARK SUITE"
echo "Host: $(hostname) | CPU: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
echo "Cores: $(nproc) | RAM: $(free -h | awk '/Mem:/{print $2}')"
echo "Kernel: $(uname -r)"
echo "Timestamp: $(date -Iseconds)"
echo "======================================================================"
echo ""

# Track all results
declare -A RESULTS

# ── Python Benchmarks ──
echo ">>> [1/7] Aviation TCAS"
python3 "$SCRIPT_DIR/aviation.py" 2>&1 | tee -a "$SCRIPT_DIR/run_${TIMESTAMP}.log"
echo ""

echo ">>> [2/7] Autonomous Vehicle Sensor Fusion"
python3 "$SCRIPT_DIR/automotive.py" 2>&1 | tee -a "$SCRIPT_DIR/run_${TIMESTAMP}.log"
echo ""

echo ">>> [3/7] Nuclear Reactor Safety"
python3 "$SCRIPT_DIR/nuclear.py" 2>&1 | tee -a "$SCRIPT_DIR/run_${TIMESTAMP}.log"
echo ""

echo ">>> [4/7] Maritime Fleet Tracking"
python3 "$SCRIPT_DIR/fleet.py" 2>&1 | tee -a "$SCRIPT_DIR/run_${TIMESTAMP}.log"
echo ""

echo ">>> [5/7] Energy Grid Monitoring"
python3 "$SCRIPT_DIR/energy.py" 2>&1 | tee -a "$SCRIPT_DIR/run_${TIMESTAMP}.log"
echo ""

echo ">>> [6/7] ICU Patient Monitoring"
python3 "$SCRIPT_DIR/medical.py" 2>&1 | tee -a "$SCRIPT_DIR/run_${TIMESTAMP}.log"
echo ""

# ── Rust VM Benchmark ──
echo ">>> [7/7] Rust VM Criterion Benchmarks"
VM_DIR="/home/phoenix/.openclaw/workspace/flux-vm-v3"
if [ -d "$VM_DIR" ]; then
    # Copy bench file into the VM benches dir
    cp "$SCRIPT_DIR/vm_bench.rs" "$VM_DIR/benches/real_world_bench.rs"
    
    # Add bench entry to Cargo.toml if not present
    if ! grep -q "real_world_bench" "$VM_DIR/Cargo.toml"; then
        echo '' >> "$VM_DIR/Cargo.toml"
        echo '[[bench]]' >> "$VM_DIR/Cargo.toml"
        echo 'name = "real_world_bench"' >> "$VM_DIR/Cargo.toml"
        echo 'harness = false' >> "$VM_DIR/Cargo.toml"
        echo 'path = "benches/real_world_bench.rs"' >> "$VM_DIR/Cargo.toml"
    fi
    
    echo "Compiling Rust benchmarks..."
    cd "$VM_DIR"
    cargo bench --bench real_world_bench 2>&1 | tee -a "$SCRIPT_DIR/run_${TIMESTAMP}.log" || echo "WARNING: Rust bench failed"
    echo ""
else
    echo "WARNING: flux-vm-v3 not found at $VM_DIR, skipping Rust benchmarks"
fi

echo "======================================================================"
echo "BENCHMARK SUITE COMPLETE"
echo "Full log: $SCRIPT_DIR/run_${TIMESTAMP}.log"
echo "======================================================================"
