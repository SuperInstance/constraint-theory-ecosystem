# FLUX REST API Deployment Guide

Quick-start guide for deploying the FLUX Constraint Engine REST API server. Get from zero to production-ready API in minutes.

## Quick Start

### 1. Install Dependencies

```bash
pip install flask flask-cors
```

### 2. Start the Server

```bash
cd src/python
python3 flux_server.py
```

The server starts on `http://localhost:8080` with test API key `test-key-123`.

### 3. Test the API

```bash
curl -H "X-API-Key: test-key-123" http://localhost:8080/health
```

## Configuration

Control the server with environment variables:

```bash
export FLUX_PORT=8080              # Server port
export FLUX_HOST=0.0.0.0          # Bind address
export FLUX_API_KEYS=key1,key2,key3  # Valid API keys
export FLASK_DEBUG=true           # Enable debug mode
```

## API Usage Examples

### Health Check

```bash
curl -H "X-API-Key: test-key-123" \
  http://localhost:8080/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.2.3",
  "uptime_seconds": 3600
}
```

### Single Value Check

Check if a temperature reading violates safety constraints:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key-123" \
  -d '{
    "constraints": [
      {"name": "temperature", "lo": 20, "hi": 80},
      {"name": "pressure", "lo": 10, "hi": 50}
    ],
    "value": 75
  }' \
  http://localhost:8080/check
```

**Response:**
```json
{
  "error_mask": 1,
  "severity": "warning",
  "violated_lo": false,
  "violated_hi": true,
  "details": [
    {
      "name": "temperature",
      "lo": 20,
      "hi": 80,
      "passed": true,
      "value": 75
    },
    {
      "name": "pressure",
      "lo": 10,
      "hi": 50,
      "passed": false,
      "value": 75,
      "violation_type": "high"
    }
  ]
}
```

### Batch Check

Process multiple sensor readings efficiently:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-key-123" \
  -d '{
    "constraints": [
      {"name": "temperature", "lo": 20, "hi": 80}
    ],
    "values": [25, 45, 85, 95]
  }' \
  http://localhost:8080/check/batch
```

**Response:**
```json
{
  "results": [
    {"value": 25, "severity": "pass", "error_mask": 0},
    {"value": 45, "severity": "pass", "error_mask": 0},
    {"value": 85, "severity": "warning", "error_mask": 1},
    {"value": 95, "severity": "critical", "error_mask": 1}
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

### List Industry Presets

```bash
curl -H "X-API-Key: test-key-123" \
  http://localhost:8080/presets
```

**Response:**
```json
{
  "presets": {
    "aviation": {
      "name": "Aviation Safety Standards",
      "description": "FAA-compliant altitude and speed constraints",
      "constraint_count": 4
    },
    "medical": {
      "name": "Medical Device Standards",
      "description": "FDA-approved medical device operational limits",
      "constraint_count": 4
    }
  }
}
```

### Get Specific Preset

```bash
curl -H "X-API-Key: test-key-123" \
  http://localhost:8080/presets/aviation
```

**Response:**
```json
{
  "name": "aviation",
  "display_name": "Aviation Safety Standards",
  "description": "FAA-compliant altitude and speed constraints for commercial aircraft",
  "version": "2.1.0",
  "constraints": [
    {
      "name": "cabin_temp_C",
      "lo": -55,
      "hi": 70,
      "unit": "",
      "description": "Operational limits for cabin_temp_C"
    }
  ]
}
```

### Performance Benchmark

Test API performance with custom parameters:

```bash
curl -H "X-API-Key: test-key-123" \
  "http://localhost:8080/benchmark?iterations=50000&constraints=5"
```

**Response:**
```json
{
  "benchmark_id": "bench_1704067200_abc123",
  "timestamp": "2024-01-01T00:00:00Z",
  "config": {
    "iterations": 50000,
    "constraint_count": 5
  },
  "results": {
    "total_checks": 250000,
    "total_duration_ms": 1423,
    "checks_per_second": 175870,
    "checks_per_second_M": 0.18,
    "avg_check_time_ns": 5692
  }
}
```

## Docker Deployment

### Dockerfile

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY src/python/ .
RUN pip install flask flask-cors

EXPOSE 8080
ENV FLUX_HOST=0.0.0.0
ENV FLUX_PORT=8080

CMD ["python", "flux_server.py"]
```

### Build and Run

```bash
docker build -t flux-api .
docker run -p 8080:8080 \
  -e FLUX_API_KEYS=prod-key-123,backup-key-456 \
  flux-api
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  flux-api:
    build: .
    ports:
      - "8080:8080"
    environment:
      - FLUX_API_KEYS=prod-key-123,backup-key-456
      - FLASK_DEBUG=false
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "-H", "X-API-Key: prod-key-123", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Run with:
```bash
docker-compose up -d
```

## Production Deployment

### Using Gunicorn

Install Gunicorn for production WSGI server:

```bash
pip install gunicorn
```

Create `gunicorn_config.py`:

```python
bind = "0.0.0.0:8080"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
max_requests = 1000
max_requests_jitter = 100
```

Run with Gunicorn:

```bash
gunicorn -c gunicorn_config.py flux_server:create_app()
```

### Nginx Reverse Proxy

Configure Nginx (`/etc/nginx/sites-available/flux-api`):

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # API timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8080/health;
        access_log off;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/flux-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Systemd Service

Create `/etc/systemd/system/flux-api.service`:

```ini
[Unit]
Description=FLUX Constraint Engine API
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/opt/flux-api
Environment=FLUX_PORT=8080
Environment=FLUX_HOST=127.0.0.1
Environment=FLUX_API_KEYS=your-production-keys
ExecStart=/opt/flux-api/venv/bin/gunicorn -c gunicorn_config.py flux_server:create_app()
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable flux-api
sudo systemctl start flux-api
```

## Security Considerations

### API Key Management

- **Generate strong keys:** Use `openssl rand -hex 32` for production keys
- **Rotate regularly:** Update keys monthly in production
- **Environment variables:** Never hardcode keys in source code
- **Monitor usage:** Log API key usage for security auditing

### Rate Limiting

For production, add rate limiting. Install Flask-Limiter:

```bash
pip install flask-limiter
```

Add to `flux_server.py`:

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)

@app.route('/check')
@limiter.limit("100 per minute")
def check_value():
    # existing code...
```

### HTTPS/TLS

Use TLS certificates in production. With Let's Encrypt:

```bash
sudo certbot --nginx -d api.yourdomain.com
```

## Monitoring and Logging

### Application Logging

Configure structured logging in `flux_server.py`:

```python
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler('/var/log/flux-api/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
```

### Health Monitoring

Monitor the `/health` endpoint:

```bash
#!/bin/bash
# health_check.sh
response=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "X-API-Key: $FLUX_API_KEY" \
  http://localhost:8080/health)

if [ $response != "200" ]; then
    echo "API health check failed: $response"
    exit 1
fi
```

### Performance Monitoring

Monitor key metrics:
- Response times per endpoint
- Request rate and status codes
- Memory and CPU usage
- API key usage patterns

Use the `/benchmark` endpoint for regular performance testing:

```bash
# Weekly performance test
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8080/benchmark?iterations=100000" | \
  jq '.results.checks_per_second_M'
```

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
sudo lsof -ti:8080 | xargs sudo kill -9
```

**Permission denied:**
```bash
sudo chown -R $USER:$USER /opt/flux-api
```

**High memory usage:**
- Reduce Gunicorn workers
- Monitor for memory leaks in long-running processes
- Consider request size limits

### Debug Mode

Enable detailed error responses:

```bash
export FLASK_DEBUG=true
python3 flux_server.py
```

### Logs

Check application logs:
```bash
tail -f /var/log/flux-api/app.log
journalctl -u flux-api -f
```

## Testing

Run the test suite:

```bash
cd src/python
pip install pytest
python -m pytest test_flux_server.py -v
```

Load testing with multiple concurrent requests:

```bash
# Install wrk
sudo apt-get install wrk

# Test single check endpoint
wrk -t4 -c100 -d30s -H "X-API-Key: test-key-123" \
  -s post_check.lua http://localhost:8080/check
```

The FLUX REST API is now production-ready with proper security, monitoring, and deployment configurations. Scale horizontally by running multiple instances behind a load balancer for high-availability deployments.