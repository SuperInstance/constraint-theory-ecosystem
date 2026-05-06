#!/usr/bin/env python3
"""Generate 10,000 golden test vectors for cross-language differential testing."""
import json, random
random.seed(42)

def saturate(v):
    return max(-127, min(127, v))

def check(constraints, value):
    val = saturate(value)
    error_mask, violated_lo, violated_hi, violated_count = 0, 0, 0, 0
    for i, c in enumerate(constraints):
        lo, hi = saturate(c['lo']), saturate(c['hi'])
        lf = val < lo
        hf = val > hi
        if lf or hf:
            error_mask |= (1 << i)
            violated_count += 1
        if lf: violated_lo |= (1 << i)
        if hf: violated_hi |= (1 << i)
    return {
        "error_mask": error_mask,
        "violated_lo": violated_lo,
        "violated_hi": violated_hi,
        "violated_count": violated_count,
        "passed": error_mask == 0
    }

vectors = []
vid = 0

# 1. Boundary values (1000)
for _ in range(167):
    lo = random.randint(-100, 50)
    hi = lo + random.randint(1, 100)
    for v in [lo-1, lo, lo+1, hi-1, hi, hi+1]:
        vectors.append({"id": vid, "value": v, "constraints": [{"lo": lo, "hi": hi}],
                       "expected": check([{"lo": lo, "hi": hi}], v)})
        vid += 1

# 2. Saturation edges (1000)
for _ in range(125):
    lo = random.randint(-50, 50)
    hi = lo + random.randint(1, 50)
    for v in [-128, -127, -1, 0, 1, 126, 127, 128]:
        vectors.append({"id": vid, "value": v, "constraints": [{"lo": lo, "hi": hi}],
                       "expected": check([{"lo": lo, "hi": hi}], v)})
        vid += 1

# 3. Random in-range (2000)
for _ in range(2000):
    n = random.randint(1, 4)
    cs = [{"lo": random.randint(-80, 20), "hi": random.randint(30, 100)} for _ in range(n)]
    lo_max = max(saturate(c['lo']) for c in cs)
    hi_min = min(saturate(c['hi']) for c in cs)
    v = random.randint(lo_max, hi_min) if lo_max <= hi_min else random.randint(-50, 50)
    vectors.append({"id": vid, "value": v, "constraints": cs, "expected": check(cs, v)})
    vid += 1

# 4. Random out-of-range (2000)
for _ in range(2000):
    n = random.randint(1, 4)
    cs = [{"lo": random.randint(10, 50), "hi": random.randint(60, 100)} for _ in range(n)]
    v = random.choice([random.randint(-128, -1), random.randint(101, 128)])
    vectors.append({"id": vid, "value": v, "constraints": cs, "expected": check(cs, v)})
    vid += 1

# 5. Multi-constraint mixed (1000)
for _ in range(1000):
    cs = [{"lo": random.randint(-100, 100), "hi": random.randint(-100, 100)} for _ in range(random.randint(2, 8))]
    for c in cs:
        if c['lo'] > c['hi']: c['lo'], c['hi'] = c['hi'], c['lo']
    v = random.randint(-128, 128)
    vectors.append({"id": vid, "value": v, "constraints": cs, "expected": check(cs, v)})
    vid += 1

# 6. Single constraint extremes (1000)
for _ in range(1000):
    lo = random.choice([-127, -100, -50, 0, 50, 100])
    hi = lo + random.randint(1, min(254, 254))
    if hi > 127: hi = 127
    v = random.randint(-128, 128)
    vectors.append({"id": vid, "value": v, "constraints": [{"lo": lo, "hi": hi}],
                   "expected": check([{"lo": lo, "hi": hi}], v)})
    vid += 1

# 7. All-pass (1000)
for _ in range(1000):
    n = random.randint(1, 6)
    lo, hi = -50, 50
    cs = [{"lo": lo - random.randint(0, 20), "hi": hi + random.randint(0, 20)} for _ in range(n)]
    v = random.randint(-50, 50)
    vectors.append({"id": vid, "value": v, "constraints": cs, "expected": check(cs, v)})
    vid += 1

# 8. All-fail (1000)
for _ in range(1000):
    n = random.randint(1, 6)
    cs = [{"lo": 10, "hi": 20} for _ in range(n)]
    v = random.choice([-128, -100, -50, 100, 127, 128])
    vectors.append({"id": vid, "value": v, "constraints": cs, "expected": check(cs, v)})
    vid += 1

print(json.dumps(vectors[:10000], indent=2))
