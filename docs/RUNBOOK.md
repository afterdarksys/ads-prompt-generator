# Prompt Generator Operational Runbook

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Common Operations](#common-operations)
- [Troubleshooting](#troubleshooting)
- [Disaster Recovery](#disaster-recovery)
- [Security](#security)

## Architecture Overview

### Components
```
┌─────────────┐
│  Internet   │
└──────┬──────┘
       │
┌──────▼──────┐
│   Ingress/  │
│     ALB     │
└──────┬──────┘
       │
┌──────▼──────┐
│    Nginx    │ (Reverse Proxy, Rate Limiting)
└──────┬──────┘
       │
┌──────▼──────┐
│   Flask +   │ (3+ replicas, auto-scaling)
│  Gunicorn   │
└──────┬──────┘
       │
┌──────▼──────┐
│    Redis    │ (Caching, Rate Limiting)
└─────────────┘
```

### Technology Stack
- **Application**: Flask 3.0.3, Python 3.11
- **WSGI Server**: Gunicorn with gthread workers
- **Reverse Proxy**: Nginx
- **Cache/Rate Limiting**: Redis 7
- **Container Runtime**: Docker
- **Orchestration**: Kubernetes
- **Monitoring**: Prometheus + Grafana
- **Logging**: Structured JSON logs

### Key Features
- Health checks: `/health` and `/ready`
- Metrics: `/metrics` (Prometheus format)
- API versioning: `/api/v1/*`
- Request tracing: X-Request-ID header
- Caching: Redis-backed response caching
- Rate limiting: 60 req/min per IP
- Security headers: CSP, HSTS, X-Frame-Options

## Deployment

### Prerequisites
- Docker and Docker Compose (local dev)
- Kubernetes cluster (production)
- Redis instance
- Domain with SSL certificate

### Local Development

```bash
# Clone repository
cd /path/to/prompt-generator

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run with Docker Compose
docker-compose up

# Access application
open http://localhost:80
```

### Docker Deployment

```bash
# Build image
docker build -t prompt-generator:v1.0.0 .

# Run container
docker run -d \
  -p 5000:5000 \
  -e FLASK_ENV=production \
  -e FLASK_DEBUG=false \
  -e SECRET_KEY=your-secret-key \
  -e REDIS_URL=redis://redis:6379/0 \
  --name prompt-generator \
  prompt-generator:v1.0.0

# Check health
curl http://localhost:5000/health
```

### Kubernetes Deployment

```bash
# Apply manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/redis.yaml

# Check rollout status
kubectl rollout status deployment/prompt-generator -n prompt-generator

# Verify pods
kubectl get pods -n prompt-generator

# Check logs
kubectl logs -f deployment/prompt-generator -n prompt-generator
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes* | - | Flask secret key (required in production) |
| `FLASK_ENV` | No | production | Environment: production, development, testing |
| `FLASK_DEBUG` | No | false | Enable debug mode (NEVER in production) |
| `FLASK_HOST` | No | 127.0.0.1 | Server bind host |
| `FLASK_PORT` | No | 5000 | Server bind port |
| `REDIS_URL` | No | redis://localhost:6379/0 | Redis connection URL |
| `CACHE_ENABLED` | No | true | Enable response caching |
| `CACHE_TTL` | No | 3600 | Cache TTL in seconds |
| `RATE_LIMIT_ENABLED` | No | true | Enable rate limiting |
| `RATE_LIMIT_PER_MINUTE` | No | 60 | Rate limit per IP per minute |
| `LOG_LEVEL` | No | INFO | Log level: DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | No | json | Log format: json or text |
| `MAX_CONTENT_LENGTH` | No | 1048576 | Max request size in bytes (1MB) |

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Monitoring

### Health Checks

**Health endpoint** (`/health`):
- Returns 200 if service is running
- Used by load balancers for routing decisions
- Fast check, no dependency validation

```bash
curl http://localhost:5000/health
# {"status": "healthy", "version": "1.0.0"}
```

**Readiness endpoint** (`/ready`):
- Returns 200 if service and dependencies are ready
- Returns 503 if any dependency is unavailable
- Used by Kubernetes for pod readiness

```bash
curl http://localhost:5000/ready
# {"status": "ready", "checks": {"cache": true}}
```

### Metrics

Prometheus metrics available at `/metrics`:

**Key Metrics:**
- `flask_http_request_total` - Total HTTP requests
- `flask_http_request_duration_seconds` - Request latency histogram
- `flask_http_request_exceptions_total` - Total exceptions
- `process_cpu_seconds_total` - CPU usage
- `process_resident_memory_bytes` - Memory usage

**Accessing metrics:**
```bash
curl http://localhost:5000/metrics
```

**Note:** In production, restrict `/metrics` access to internal networks only.

### Logging

Logs are structured JSON (or text in development):

```json
{
  "event": "request_received",
  "method": "POST",
  "path": "/api/v1/generate",
  "ip": "192.168.1.1",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-01-10T12:00:00.123456Z"
}
```

**Viewing logs:**

```bash
# Docker
docker logs -f prompt-generator

# Kubernetes
kubectl logs -f deployment/prompt-generator -n prompt-generator

# Follow specific pod
kubectl logs -f pod/prompt-generator-xyz123 -n prompt-generator

# Grep for errors
kubectl logs deployment/prompt-generator -n prompt-generator | grep '"level":"error"'
```

## Common Operations

### Scaling

**Manual scaling (Kubernetes):**
```bash
kubectl scale deployment/prompt-generator --replicas=5 -n prompt-generator
```

**Auto-scaling is configured:**
- Min replicas: 3
- Max replicas: 10
- Target CPU: 70%
- Target Memory: 80%

### Rollout/Rollback

**Deploy new version:**
```bash
kubectl set image deployment/prompt-generator \
  prompt-generator=prompt-generator:v1.1.0 \
  -n prompt-generator

kubectl rollout status deployment/prompt-generator -n prompt-generator
```

**Rollback to previous version:**
```bash
kubectl rollout undo deployment/prompt-generator -n prompt-generator

# Rollback to specific revision
kubectl rollout history deployment/prompt-generator -n prompt-generator
kubectl rollout undo deployment/prompt-generator --to-revision=2 -n prompt-generator
```

### Cache Management

**Clear cache (Redis):**
```bash
# Connect to Redis
kubectl exec -it statefulset/redis -n prompt-generator -- redis-cli

# In Redis CLI:
FLUSHDB  # Clear current database
```

**Check cache stats:**
```bash
kubectl exec -it statefulset/redis -n prompt-generator -- redis-cli INFO stats
```

### Configuration Updates

**Update ConfigMap:**
```bash
kubectl edit configmap prompt-generator-config -n prompt-generator

# Restart pods to pick up changes
kubectl rollout restart deployment/prompt-generator -n prompt-generator
```

**Update Secrets:**
```bash
# Generate new secret key
NEW_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

kubectl create secret generic prompt-generator-secrets \
  --from-literal=SECRET_KEY=$NEW_KEY \
  --from-literal=REDIS_URL=redis://redis:6379/0 \
  --dry-run=client -o yaml | kubectl apply -f - -n prompt-generator

# Restart to use new secret
kubectl rollout restart deployment/prompt-generator -n prompt-generator
```

## Troubleshooting

### High Latency

**Symptoms:** Requests taking longer than expected (>100ms p95)

**Diagnosis:**
1. Check application metrics:
   ```bash
   curl http://localhost:5000/metrics | grep flask_http_request_duration
   ```
2. Check CPU/memory usage:
   ```bash
   kubectl top pods -n prompt-generator
   ```
3. Check Redis connection:
   ```bash
   kubectl exec -it statefulset/redis -n prompt-generator -- redis-cli PING
   ```

**Solutions:**
- Scale up replicas if CPU > 70%
- Check cache hit rate - low hit rate increases latency
- Verify network connectivity to Redis
- Check for slow queries in logs

### High Error Rate

**Symptoms:** 5xx errors, exceptions in logs

**Diagnosis:**
1. Check application logs:
   ```bash
   kubectl logs deployment/prompt-generator -n prompt-generator | grep '"level":"error"'
   ```
2. Check error metrics:
   ```bash
   curl http://localhost:5000/metrics | grep flask_http_request_exceptions
   ```
3. Check readiness:
   ```bash
   curl http://localhost:5000/ready
   ```

**Solutions:**
- Check for specific error patterns in logs
- Verify all environment variables are set correctly
- Check Redis connectivity
- Review recent deployments - may need rollback

### Rate Limiting Issues

**Symptoms:** 429 errors, users complaining about "Rate limit exceeded"

**Diagnosis:**
```bash
# Check rate limit metrics
curl http://localhost:5000/metrics | grep rate_limit

# Check Nginx logs
kubectl logs deployment/nginx -n prompt-generator | grep "limiting requests"
```

**Solutions:**
- Adjust rate limits: Update `RATE_LIMIT_PER_MINUTE` env var
- Implement per-user authentication for higher limits
- Add IP allowlist for trusted sources
- Consider using API keys for rate limiting

### Memory Leaks

**Symptoms:** Memory usage growing over time, OOMKilled pods

**Diagnosis:**
```bash
# Monitor memory over time
kubectl top pods -n prompt-generator --watch

# Check pod events
kubectl describe pod prompt-generator-xyz123 -n prompt-generator
```

**Solutions:**
- Restart pods as temporary fix
- Review recent code changes
- Enable memory profiling in development
- Adjust memory limits if legitimate usage

### Redis Connection Issues

**Symptoms:** Cache errors in logs, poor performance

**Diagnosis:**
```bash
# Check Redis pod
kubectl get pod -l app=redis -n prompt-generator

# Test connection
kubectl exec -it statefulset/redis -n prompt-generator -- redis-cli PING

# Check logs
kubectl logs statefulset/redis -n prompt-generator
```

**Solutions:**
- Verify Redis service is running
- Check network policies allow connections
- Verify `REDIS_URL` environment variable
- Restart Redis if unresponsive

## Disaster Recovery

### RTO/RPO

- **RTO (Recovery Time Objective):** 15 minutes
- **RPO (Recovery Point Objective):** 0 (stateless application)

### Backup Strategy

The application is **stateless** - no data backup needed.

**Configuration backup:**
- Store ConfigMaps and Secrets in version control (encrypted)
- Use Infrastructure as Code for reproducibility

### Recovery Procedures

**Complete service failure:**

1. Check cluster health:
   ```bash
   kubectl get nodes
   kubectl get pods -n prompt-generator
   ```

2. Redeploy application:
   ```bash
   kubectl delete namespace prompt-generator
   kubectl apply -f k8s/deployment.yaml
   kubectl apply -f k8s/redis.yaml
   ```

3. Verify health:
   ```bash
   kubectl get pods -n prompt-generator
   curl https://prompt-generator.example.com/health
   ```

**Redis data loss:**

Redis is used only for caching - data loss acceptable. Cache will rebuild automatically.

### Failover Procedures

**Multi-region setup (if configured):**

1. Update DNS to point to backup region
2. Verify backup region health
3. Monitor traffic shift in Grafana
4. Investigate and fix primary region

## Security

### Security Checklist

- [ ] `SECRET_KEY` is randomly generated and not default value
- [ ] `FLASK_DEBUG` is `false` in production
- [ ] HTTPS is enforced (TLS 1.2+)
- [ ] Security headers are configured (CSP, HSTS, X-Frame-Options)
- [ ] Rate limiting is enabled
- [ ] Input validation is working
- [ ] Container runs as non-root user (UID 1000)
- [ ] Read-only root filesystem
- [ ] Network policies restrict pod-to-pod communication
- [ ] Secrets are stored in Kubernetes Secrets (not ConfigMaps)
- [ ] `/metrics` endpoint is restricted to internal network
- [ ] Dependency vulnerabilities are scanned regularly

### Security Incidents

**Suspected security breach:**

1. Immediately revoke all secrets:
   ```bash
   # Rotate SECRET_KEY
   kubectl delete secret prompt-generator-secrets -n prompt-generator
   # Create new secret (follow "Configuration Updates" above)
   ```

2. Check logs for suspicious activity:
   ```bash
   kubectl logs deployment/prompt-generator -n prompt-generator \
     --since=24h | grep -E "(error|unauthorized|forbidden)"
   ```

3. Review metrics for anomalies (unusual traffic patterns)

4. If compromised:
   - Take affected pods offline
   - Preserve logs for forensics
   - Rebuild from clean images
   - Update all credentials

### Vulnerability Management

**Regular scans:**
```bash
# Dependency scan
safety check --file requirements.txt

# Container image scan
trivy image prompt-generator:latest
```

**Update process:**
1. Monitor security advisories
2. Test updates in staging
3. Deploy during maintenance window
4. Verify functionality post-deployment

## Contacts and Escalation

**On-Call:** [PagerDuty/Opsgenie link]
**Slack Channel:** #prompt-generator-ops
**Documentation:** https://github.com/yourorg/prompt-generator

**Escalation Path:**
1. L1: On-call engineer
2. L2: Senior SRE
3. L3: Engineering manager
4. L4: CTO

## Appendix

### Useful Commands

```bash
# Get all resources
kubectl get all -n prompt-generator

# Describe deployment
kubectl describe deployment prompt-generator -n prompt-generator

# Get events
kubectl get events -n prompt-generator --sort-by='.lastTimestamp'

# Port forward for local testing
kubectl port-forward svc/prompt-generator 5000:80 -n prompt-generator

# Execute command in pod
kubectl exec -it deployment/prompt-generator -n prompt-generator -- /bin/bash

# Copy file from pod
kubectl cp prompt-generator-xyz123:/app/logs/app.log ./app.log -n prompt-generator
```

### Performance Baselines

| Metric | Target | Alert Threshold |
|--------|--------|----------------|
| p50 latency | < 50ms | > 100ms |
| p95 latency | < 100ms | > 200ms |
| p99 latency | < 200ms | > 500ms |
| Error rate | < 0.1% | > 1% |
| Availability | > 99.9% | < 99.5% |
| Cache hit rate | > 80% | < 50% |

### Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-10 | 1.0.0 | Initial production release |
