"""
Financial: Trading System Risk Checks
Real system: FIX protocol engines validate order parameters.
Tests FLUX constraint engine against high-frequency trading constraints.
"""
import sys
import os
import sys
import random
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flux_scaling import ScaledConstraint, run_benchmark, BenchmarkResult

# FIX order constraints
FIX_CONSTRAINTS = [
    ("price", 0.01, 999999.99),
    ("quantity", 1.0, 1000000.0),
    ("notional", 0.01, 10000000.0),       # price × qty
    ("price_deviation_pct", -10.0, 10.0),  # % from last price
    ("order_rate", 0.0, 1000.0),           # orders/sec
]

N_ORDERS = 100_000
VIOLATION_RATE = 0.001
LAST_PRICE = 150.0  # Reference price


def generate_order_data(n: int) -> list:
    """Generate realistic trading orders with 0.1% violations."""
    records = []
    order_count_per_sec = 0
    for i in range(n):
        # Normal order
        price = LAST_PRICE * random.gauss(1.0, 0.01)  # ±1% of last
        qty = random.lognormvariate(math.log(100), 1.5)  # Log-normal quantity
        qty = max(1, min(1000000, qty))
        notional = price * qty
        deviation = ((price - LAST_PRICE) / LAST_PRICE) * 100

        # Reset order rate counter every ~1000 orders
        if i % 1000 == 0:
            order_count_per_sec = random.randint(50, 800)
        else:
            order_count_per_sec += 1

        # Inject violation
        if random.random() < VIOLATION_RATE:
            field = random.choice(["price", "quantity", "notional", "price_deviation_pct", "order_rate"])
            if field == "price":
                price = random.choice([0.001, -5.0, 2000000.0])
                notional = price * qty
                deviation = ((price - LAST_PRICE) / LAST_PRICE) * 100
            elif field == "quantity":
                qty = random.choice([0, -10, 5000000.0])
                notional = price * qty
            elif field == "notional":
                qty = 20000000.0 / price  # Force huge notional
                notional = price * qty
            elif field == "price_deviation_pct":
                price = LAST_PRICE * (1 + random.choice([-0.20, 0.20, -0.50, 0.50]))
                notional = price * qty
                deviation = ((price - LAST_PRICE) / LAST_PRICE) * 100
            elif field == "order_rate":
                order_count_per_sec = random.randint(1500, 5000)

        records.append({
            "price": price,
            "quantity": qty,
            "notional": notional,
            "price_deviation_pct": deviation,
            "order_rate": float(order_count_per_sec),
        })
    return records


def test_fix_basic():
    """Test basic order validation."""
    scaled = [ScaledConstraint(name=n, lo_real=lo, hi_real=hi) for n, lo, hi in FIX_CONSTRAINTS]

    # Valid order
    valid = {"price": 150.0, "quantity": 100.0, "notional": 15000.0, "price_deviation_pct": 0.5, "order_rate": 500.0}
    for sc in scaled:
        flux_passed, naive = sc.check(valid[sc.name])
        assert naive, f"Valid order flagged for {sc.name}"

    # Invalid order
    invalid = {"price": -50000.0, "quantity": 100.0, "notional": -500.0, "price_deviation_pct": -5.0, "order_rate": 500.0}
    flux_passed, naive = scaled[0].check(invalid["price"])
    assert not naive, "Negative price should fail"
    assert not flux_passed, "Negative price should fail FLUX"

    print("✓ FIX basic tests passed")


def test_fix_benchmark():
    """Full benchmark: 100,000 orders, 0.1% violations."""
    result = run_benchmark(
        domain="Financial (FIX)",
        constraints=FIX_CONSTRAINTS,
        data_generator=generate_order_data,
        required_rate=1_000_000,  # HFT needs >1M checks/sec
        n_records=N_ORDERS,
    )

    print(f"\n{'='*60}")
    print(f"Financial FIX Benchmark — {N_ORDERS:,} orders, {VIOLATION_RATE*100}% violations")
    print(f"{'='*60}")
    print(f"  Total checks:    {result.total_checks:,}")
    print(f"  FLUX throughput:  {result.flux_throughput:,.0f} checks/sec")
    print(f"  Naive throughput: {result.naive_throughput:,.0f} checks/sec")
    print(f"  Headroom:         {result.headroom:.1f}x required rate")
    print(f"  p50 latency:      {result.p50_latency_us:.2f} μs")
    print(f"  p95 latency:      {result.p95_latency_us:.2f} μs")
    print(f"  p99 latency:      {result.p99_latency_us:.2f} μs")
    print(f"  False positives:  {result.false_positives} ({result.false_positive_rate:.4%})")
    print(f"  False negatives:  {result.false_negatives} ({result.false_negative_rate:.4%})")
    print(f"  Accuracy:         {result.accuracy:.4%}")

    return result


if __name__ == "__main__":
    random.seed(42)
    test_fix_basic()
    result = test_fix_benchmark()
    print(f"\n✓ All FIX tests completed")
