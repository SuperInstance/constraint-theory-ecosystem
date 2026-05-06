# flux-constraint

INT8 saturated constraint checking for safety-critical systems.

```python
from flux_constraint import FluxConstraint

fc = FluxConstraint.from_preset("aviation")
result = fc.check(70)
print(result.severity)  # Severity.CAUTION
print(result.passed)    # False
```

- Zero dependencies
- 10 industry presets (aviation, medical, maritime, automotive, energy, nuclear, railway, robotics, space, underwater)
- 62 billion checks/sec on GPU (CUDA kernel included separately)
- 60 million differential test inputs, zero mismatches
- Formally proven with 15 Coq theorems
- DO-178C DAL A, ISO 26262 ASIL-D certification path

See https://github.com/SuperInstance/constraint-theory-ecosystem
