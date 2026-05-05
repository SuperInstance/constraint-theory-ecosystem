# FLUX Constraint Engine REST API Reference

The FLUX Constraint Engine provides a high-performance REST API for constraint validation, supporting both single and batch operations with industry-standard presets.

## Base URL

```
https://api.fluxconstraint.com/v1
```

## Authentication

All API requests require an API key sent in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key-here" https://api.fluxconstraint.com/v1/health
```

## Rate Limiting

- **Free Tier**: 1,000 requests/hour
- **Pro Tier**: 10,000 requests/hour
- **Enterprise**: Custom limits

Rate limit headers are included in all responses:
- `X-RateLimit-Limit`: Total requests allowed per hour
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid request format or parameters |
| 401 | Unauthorized | Missing or invalid API key |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error occurred |

Error responses follow this format:

```json
{
  "error": {
    "code": "INVALID_CONSTRAINT",
    "message": "Constraint 'temperature' has invalid range: lo must be less than hi",
    "details": {
      "constraint": "temperature",
      "lo": 100,
      "hi": 50
    }
  }
}
```

## Endpoints

### POST /check

Check a single value against a set of constraints.

#### Request Body

```json
{
  "constraints": [
    {
      "name": "temperature",
      "lo": 20.0,
      "hi": 80.0
    },
    {
      "name": "pressure",
      "lo": 10.0,
      "hi": 50.0
    }
  ],
  "value": 75
}
```

#### Response

```json
{
  "error_mask": 1,
  "severity": "warning",
  "violated_lo": false,
  "violated_hi": true,
  "details": [
    {
      "name": "temperature",
      "lo": 20.0,
      "hi": 80.0,
      "passed": true,
      "value": 75
    },
    {
      "name": "pressure",
      "lo": 10.0,
      "hi": 50.0,
      "passed": false,
      "value": 75,
      "violation_type": "high"
    }
  ]
}
```

#### Example curl

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "constraints": [
      {"name": "temp", "lo": 20, "hi": 80}
    ],
    "value": 75
  }' \
  https://api.fluxconstraint.com/v1/check
```

#### Severity Levels

- `pass`: All constraints satisfied
- `caution`: Minor violations, system operational
- `warning`: Significant violations, attention needed
- `critical`: Severe violations, immediate action required

### POST /check/batch

Check multiple values against constraints in a single request for improved performance.

#### Request Body

```json
{
  "constraints": [
    {
      "name": "temperature",
      "lo": 20.0,
      "hi": 80.0
    },
    {
      "name": "pressure",
      "lo": 10.0,
      "hi": 50.0
    }
  ],
  "values": [25, 45, 75, 95]
}
```

#### Response

```json
{
  "results": [
    {
      "value": 25,
      "error_mask": 0,
      "severity": "pass",
      "violated_lo": false,
      "violated_hi": false,
      "details": [
        {
          "name": "temperature",
          "lo": 20.0,
          "hi": 80.0,
          "passed": true,
          "value": 25
        },
        {
          "name": "pressure",
          "lo": 10.0,
          "hi": 50.0,
          "passed": true,
          "value": 25
        }
      ]
    },
    {
      "value": 95,
      "error_mask": 3,
      "severity": "critical",
      "violated_lo": false,
      "violated_hi": true,
      "details": [
        {
          "name": "temperature",
          "lo": 20.0,
          "hi": 80.0,
          "passed": false,
          "value": 95,
          "violation_type": "high"
        },
        {
          "name": "pressure",
          "lo": 10.0,
          "hi": 50.0,
          "passed": false,
          "value": 95,
          "violation_type": "high"
        }
      ]
    }
  ],
  "stats": {
    "total": 4,
    "pass": 2,
    "caution": 0,
    "warning": 1,
    "critical": 1
  }
}
```

#### Example curl

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "constraints": [
      {"name": "temp", "lo": 20, "hi": 80}
    ],
    "values": [25, 45, 75, 95]
  }' \
  https://api.fluxconstraint.com/v1/check/batch
```

### GET /presets

List all available industry constraint presets.

#### Response

```json
{
  "presets": {
    "aviation": {
      "name": "Aviation Safety Standards",
      "description": "FAA-compliant altitude and speed constraints",
      "constraint_count": 8
    },
    "medical": {
      "name": "Medical Device Standards",
      "description": "FDA-approved medical device operational limits",
      "constraint_count": 12
    },
    "automotive": {
      "name": "Automotive Safety",
      "description": "ISO 26262 functional safety constraints",
      "constraint_count": 15
    },
    "nuclear": {
      "name": "Nuclear Reactor Safety",
      "description": "Nuclear regulatory commission safety limits",
      "constraint_count": 20
    }
  }
}
```

#### Example curl

```bash
curl -H "X-API-Key: your-api-key" \
  https://api.fluxconstraint.com/v1/presets
```

### GET /presets/{name}

Get detailed constraint definitions for a specific preset.

#### Path Parameters

- `name` (string): Preset identifier (aviation, medical, automotive, nuclear)

#### Response

```json
{
  "name": "aviation",
  "display_name": "Aviation Safety Standards",
  "description": "FAA-compliant altitude and speed constraints for commercial aircraft",
  "version": "2.1.0",
  "last_updated": "2024-03-15T10:30:00Z",
  "constraints": [
    {
      "name": "altitude_ft",
      "lo": 0,
      "hi": 42000,
      "unit": "feet",
      "description": "Maximum certified altitude for commercial aircraft"
    },
    {
      "name": "airspeed_kts",
      "lo": 60,
      "hi": 250,
      "unit": "knots",
      "description": "Airspeed limits below 10,000ft"
    },
    {
      "name": "cabin_pressure_psi",
      "lo": 10.9,
      "hi": 14.7,
      "unit": "psi",
      "description": "Cabin pressurization safety limits"
    }
  ]
}
```

#### Example curl

```bash
curl -H "X-API-Key: your-api-key" \
  https://api.fluxconstraint.com/v1/presets/aviation
```

### GET /benchmark

Run a performance benchmark to measure constraint checking throughput.

#### Query Parameters

- `iterations` (integer, optional): Number of benchmark iterations (default: 100000)
- `constraints` (integer, optional): Number of constraints to test (default: 10)

#### Response

```json
{
  "benchmark_id": "bench_1704067200_abc123",
  "timestamp": "2024-01-01T00:00:00Z",
  "config": {
    "iterations": 100000,
    "constraint_count": 10,
    "value_range": [-1000, 1000]
  },
  "results": {
    "total_checks": 1000000,
    "total_duration_ms": 2847,
    "checks_per_second": 351370,
    "checks_per_second_M": 0.35,
    "avg_check_time_ns": 2847,
    "memory_usage_mb": 45.2
  },
  "environment": {
    "server_region": "us-east-1",
    "cpu_cores": 8,
    "memory_gb": 32
  }
}
```

#### Example curl

```bash
curl -H "X-API-Key: your-api-key" \
  "https://api.fluxconstraint.com/v1/benchmark?iterations=50000&constraints=5"
```

### GET /health

Health check endpoint for monitoring service status.

#### Response

```json
{
  "status": "healthy",
  "version": "1.2.3",
  "uptime_seconds": 86400,
  "timestamp": "2024-01-01T12:00:00Z",
  "database": {
    "status": "connected",
    "response_time_ms": 12
  },
  "cache": {
    "status": "operational",
    "hit_rate": 0.94
  }
}
```

#### Example curl

```bash
curl -H "X-API-Key: your-api-key" \
  https://api.fluxconstraint.com/v1/health
```

## Client Examples

### Python Client

```python
import requests
import json

class FluxConstraintClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.fluxconstraint.com/v1"
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }

    def check_value(self, constraints, value):
        """Check single value against constraints"""
        payload = {
            "constraints": constraints,
            "value": value
        }
        response = requests.post(
            f"{self.base_url}/check",
            headers=self.headers,
            json=payload
        )
        return response.json()

    def check_batch(self, constraints, values):
        """Check multiple values against constraints"""
        payload = {
            "constraints": constraints,
            "values": values
        }
        response = requests.post(
            f"{self.base_url}/check/batch",
            headers=self.headers,
            json=payload
        )
        return response.json()

    def get_presets(self):
        """Get list of available presets"""
        response = requests.get(
            f"{self.base_url}/presets",
            headers=self.headers
        )
        return response.json()

# Usage example
client = FluxConstraintClient("your-api-key")

constraints = [
    {"name": "temperature", "lo": 20, "hi": 80},
    {"name": "pressure", "lo": 10, "hi": 50}
]

result = client.check_value(constraints, 75)
print(f"Severity: {result['severity']}")
```

### JavaScript Client

```javascript
class FluxConstraintClient {
    constructor(apiKey) {
        this.apiKey = apiKey;
        this.baseUrl = 'https://api.fluxconstraint.com/v1';
        this.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': apiKey
        };
    }

    async checkValue(constraints, value) {
        const response = await fetch(`${this.baseUrl}/check`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                constraints: constraints,
                value: value
            })
        });
        return await response.json();
    }

    async checkBatch(constraints, values) {
        const response = await fetch(`${this.baseUrl}/check/batch`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                constraints: constraints,
                values: values
            })
        });
        return await response.json();
    }

    async getPresets() {
        const response = await fetch(`${this.baseUrl}/presets`, {
            headers: this.headers
        });
        return await response.json();
    }
}

// Usage example
const client = new FluxConstraintClient('your-api-key');

const constraints = [
    { name: 'temperature', lo: 20, hi: 80 },
    { name: 'pressure', lo: 10, hi: 50 }
];

client.checkValue(constraints, 75)
    .then(result => console.log(`Severity: ${result.severity}`))
    .catch(error => console.error('Error:', error));
```

## OpenAPI 3.0 Specification

```yaml
openapi: 3.0.3
info:
  title: FLUX Constraint Engine API
  description: High-performance constraint validation service
  version: 1.2.3
  contact:
    name: FLUX Support
    email: support@fluxconstraint.com
    url: https://docs.fluxconstraint.com

servers:
  - url: https://api.fluxconstraint.com/v1
    description: Production server

security:
  - ApiKeyAuth: []

paths:
  /check:
    post:
      summary: Check single value against constraints
      operationId: checkValue
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CheckRequest'
      responses:
        '200':
          description: Constraint check result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CheckResponse'
        '400':
          description: Invalid request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /check/batch:
    post:
      summary: Check multiple values against constraints
      operationId: checkBatch
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BatchCheckRequest'
      responses:
        '200':
          description: Batch constraint check results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BatchCheckResponse'

  /presets:
    get:
      summary: List available constraint presets
      operationId: getPresets
      responses:
        '200':
          description: List of available presets
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PresetsResponse'

  /presets/{name}:
    get:
      summary: Get specific constraint preset
      operationId: getPreset
      parameters:
        - name: name
          in: path
          required: true
          schema:
            type: string
          example: aviation
      responses:
        '200':
          description: Constraint preset details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PresetResponse'

components:
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key

  schemas:
    Constraint:
      type: object
      required:
        - name
        - lo
        - hi
      properties:
        name:
          type: string
          description: Constraint identifier
        lo:
          type: number
          description: Lower bound (inclusive)
        hi:
          type: number
          description: Upper bound (inclusive)
        unit:
          type: string
          description: Optional unit of measurement

    CheckRequest:
      type: object
      required:
        - constraints
        - value
      properties:
        constraints:
          type: array
          items:
            $ref: '#/components/schemas/Constraint'
        value:
          type: number
          description: Value to check against constraints

    CheckResponse:
      type: object
      properties:
        error_mask:
          type: integer
          description: Bitmask indicating which constraints were violated
        severity:
          type: string
          enum: [pass, caution, warning, critical]
        violated_lo:
          type: boolean
        violated_hi:
          type: boolean
        details:
          type: array
          items:
            $ref: '#/components/schemas/ConstraintDetail'
```

This API reference provides comprehensive documentation for integrating with the FLUX Constraint Engine, supporting both simple single-value checks and high-performance batch operations with industry-standard presets for critical applications.