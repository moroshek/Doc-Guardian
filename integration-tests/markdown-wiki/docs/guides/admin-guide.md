# Administrator Guide

Guide for deploying and operating DataFlow in production.

**Last Updated:** 2025-01-10

## Table of Contents

- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Performance Tuning](#performance)
- [Security](#security)
- [Backup and Recovery](#backup-and-recovery)
- [Troubleshooting](#troubleshooting)

## Deployment

### Kubernetes Deployment

Deploy DataFlow on Kubernetes using Helm:

```bash
# Add Helm repository
helm repo add dataflow https://charts.dataflow.io
helm repo update

# Install
helm install dataflow dataflow/dataflow \
  --set workers=16 \
  --set memory=32Gi \
  --set persistence.enabled=true
```

**Helm values** (`values.yaml`):
```yaml
workers: 16
memory: 32Gi

persistence:
  enabled: true
  storageClass: fast-ssd
  size: 100Gi

monitoring:
  metrics:
    enabled: true
    serviceMonitor: true

resources:
  limits:
    cpu: 8
    memory: 32Gi
  requests:
    cpu: 4
    memory: 16Gi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPU: 70
```

### Docker Deployment

Run DataFlow in Docker:

```bash
docker run -d \
  --name dataflow \
  -p 8080:8080 \
  -v /data:/data \
  -v /config:/config \
  -e DATAFLOW_WORKERS=8 \
  dataflow/dataflow:latest
```

**Docker Compose** (`docker-compose.yml`):
```yaml
version: '3.8'

services:
  dataflow:
    image: dataflow/dataflow:latest
    ports:
      - "8080:8080"
      - "9090:9090"  # Metrics
    volumes:
      - ./data:/data
      - ./config:/config
      - checkpoints:/var/dataflow/checkpoints
    environment:
      - DATAFLOW_WORKERS=8
      - DATAFLOW_MEMORY=16GB
    restart: unless-stopped

  prometheus:
    image: prom/prometheus
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  checkpoints:
  prometheus_data:
  grafana_data:
```

### Bare Metal Deployment

Install as a systemd service:

```bash
# Install
sudo apt-get install dataflow

# Configure
sudo vi /etc/dataflow/config.yaml

# Enable and start
sudo systemctl enable dataflow
sudo systemctl start dataflow

# Check status
sudo systemctl status dataflow
```

**Systemd unit** (`/etc/systemd/system/dataflow.service`):
```ini
[Unit]
Description=DataFlow Service
After=network.target

[Service]
Type=simple
User=dataflow
Group=dataflow
ExecStart=/usr/bin/dataflow run --config /etc/dataflow/config.yaml
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Monitoring

### Metrics

DataFlow exposes Prometheus metrics at `/metrics`:

**Key metrics:**
- `dataflow_pipeline_running` - Number of running pipelines
- `dataflow_events_processed_total` - Total events processed
- `dataflow_events_failed_total` - Failed events
- `dataflow_pipeline_latency_seconds` - Processing latency
- `dataflow_memory_used_bytes` - Memory usage
- `dataflow_checkpoint_duration_seconds` - Checkpoint time

**Prometheus config** (`prometheus.yml`):
```yaml
scrape_configs:
  - job_name: 'dataflow'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 10s
```

### Logging

Configure structured logging:

```yaml
# config.yaml
monitoring:
  logging:
    level: info
    format: json
    output: /var/log/dataflow/dataflow.log
    rotation:
      max_size: 100MB
      max_age: 30d
      max_backups: 10
```

**Log levels:**
- `debug` - Verbose debugging information
- `info` - General informational messages (default)
- `warn` - Warning messages
- `error` - Error messages
- `fatal` - Fatal errors that cause shutdown

### Tracing

Enable distributed tracing with Jaeger:

```yaml
monitoring:
  tracing:
    enabled: true
    backend: jaeger
    jaeger:
      endpoint: http://jaeger:14268/api/traces
      sample_rate: 0.1  # Sample 10% of traces
```

### Dashboards

Import Grafana dashboards:

```bash
# Import official dashboard
grafana-cli plugins install dataflow-datasource
# Dashboard ID: 12345
```

**Key dashboard panels:**
- Pipeline throughput
- Event latency histogram
- Error rate
- Memory usage
- CPU usage
- Checkpoint duration

### Alerting

Configure alerts in Prometheus:

```yaml
# alerts.yml
groups:
  - name: dataflow
    rules:
      - alert: HighErrorRate
        expr: rate(dataflow_events_failed_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High error rate in DataFlow

      - alert: HighLatency
        expr: histogram_quantile(0.99, dataflow_pipeline_latency_seconds) > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: High p99 latency

      - alert: PipelineDown
        expr: up{job="dataflow"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: DataFlow is down
```

## Performance Tuning {#performance}

### Worker Configuration

Tune worker count and memory:

```yaml
runtime:
  workers: 16  # Number of CPU cores
  worker_memory: 2GB  # Memory per worker

  # JVM options (if using JVM runtime)
  jvm_options:
    - "-XX:+UseG1GC"
    - "-XX:MaxGCPauseMillis=200"
```

**Guidelines:**
- Workers = CPU cores (for CPU-bound workloads)
- Workers = 2x CPU cores (for I/O-bound workloads)
- Worker memory = Total memory / workers

### Buffer Tuning

Configure buffering for throughput:

```yaml
runtime:
  performance:
    buffer_size: 10000
    batch_size: 1000
    prefetch_count: 100
    backpressure_threshold: 0.8
```

### Network Tuning

Optimize network performance:

```yaml
runtime:
  network:
    tcp_nodelay: true
    tcp_keepalive: true
    send_buffer_size: 1MB
    receive_buffer_size: 1MB
```

### Checkpoint Optimization

Tune checkpointing:

```yaml
runtime:
  checkpoint_interval: 60s  # More frequent = lower recovery time
  checkpoint_compression: true  # Reduces I/O
  checkpoint_async: true  # Don't block processing
```

### Kafka Optimization

Tune Kafka connectors:

```yaml
sources:
  kafka:
    fetch_min_bytes: 1MB
    fetch_max_wait_ms: 500
    max_poll_records: 1000

sinks:
  kafka:
    batch_size: 32KB
    linger_ms: 10
    compression_type: snappy
    acks: 1  # 0=none, 1=leader, all=all replicas
```

## Security

### Authentication

Enable authentication:

```yaml
security:
  authentication:
    enabled: true
    method: oauth2
    oauth2:
      issuer_url: https://auth.example.com
      client_id: dataflow
      client_secret: ${OAUTH_SECRET}
```

**Supported methods:**
- `basic` - Basic HTTP authentication
- `oauth2` - OAuth 2.0 / OpenID Connect
- `jwt` - JWT tokens
- `mtls` - Mutual TLS

### Authorization

Configure RBAC policies:

```yaml
# policies.yaml
policies:
  - role: admin
    permissions:
      - pipeline:create
      - pipeline:delete
      - pipeline:read
      - pipeline:update
      - config:write

  - role: user
    permissions:
      - pipeline:read
      - pipeline:create

  - role: viewer
    permissions:
      - pipeline:read
```

### TLS/SSL

Enable TLS:

```yaml
runtime:
  tls:
    enabled: true
    cert: /etc/dataflow/certs/server.crt
    key: /etc/dataflow/certs/server.key
    ca: /etc/dataflow/certs/ca.crt
    verify_client: true
```

### Secrets Management

Use secrets from external providers:

```yaml
secrets:
  provider: vault
  vault:
    address: https://vault.example.com
    token: ${VAULT_TOKEN}
    mount_path: secret/dataflow
```

**Supported providers:**
- `vault` - HashiCorp Vault
- `aws-secrets-manager` - AWS Secrets Manager
- `azure-keyvault` - Azure Key Vault
- `gcp-secret-manager` - GCP Secret Manager

## Backup and Recovery

### Checkpoint Backup

Back up checkpoint data:

```bash
# Create backup
tar -czf checkpoints-$(date +%Y%m%d).tar.gz /var/dataflow/checkpoints

# Restore backup
tar -xzf checkpoints-20250110.tar.gz -C /var/dataflow/
```

### State Export

Export pipeline state:

```bash
# Export state
dataflow state export --pipeline my-pipeline --output state.json

# Import state
dataflow state import --pipeline my-pipeline --input state.json
```

### Disaster Recovery

Configure disaster recovery:

```yaml
runtime:
  disaster_recovery:
    enabled: true
    backup_interval: 1h
    backup_location: s3://backups/dataflow
    retention_days: 30
```

## Troubleshooting

### High Memory Usage

**Symptoms:**
- Out of memory errors
- Slow performance
- Frequent GC pauses

**Solutions:**
```yaml
# Increase memory
runtime:
  memory: 64GB

# Reduce batch sizes
runtime:
  performance:
    batch_size: 500

# Enable memory-efficient mode
runtime:
  memory_mode: conservative
```

### High Latency

**Symptoms:**
- Slow event processing
- Growing backlog

**Solutions:**
```yaml
# Increase workers
runtime:
  workers: 32

# Tune buffers
runtime:
  performance:
    buffer_size: 20000
    prefetch_count: 200
```

### Connection Issues

**Symptoms:**
- "Connection refused" errors
- Timeouts

**Solutions:**
```yaml
# Increase timeouts
sources:
  kafka:
    request_timeout_ms: 60000
    session_timeout_ms: 30000

# Add retries
runtime:
  retry:
    max_attempts: 5
    backoff: exponential
```

For more troubleshooting, see [Troubleshooting Guide](troubleshooting.md).

## Capacity Planning

### Sizing Guidelines

**Small deployment (dev/test):**
- Workers: 2-4
- Memory: 4-8GB
- Disk: 20GB

**Medium deployment (production):**
- Workers: 8-16
- Memory: 16-32GB
- Disk: 100GB

**Large deployment (enterprise):**
- Workers: 32-64
- Memory: 64-128GB
- Disk: 500GB+

### Scaling Guidelines

**Vertical scaling:**
- Increase workers and memory on single instance
- Good for: Single large pipelines

**Horizontal scaling:**
- Deploy multiple DataFlow instances
- Use load balancer
- Good for: Multiple independent pipelines

## Maintenance

### Upgrades

Upgrade DataFlow:

```bash
# Kubernetes
helm upgrade dataflow dataflow/dataflow --version 2.5.0

# Docker
docker pull dataflow/dataflow:2.5.0
docker-compose up -d

# Bare metal
sudo apt-get update
sudo apt-get install dataflow=2.5.0
sudo systemctl restart dataflow
```

**Upgrade checklist:**
1. Review release notes
2. Test in staging environment
3. Back up checkpoints
4. Perform upgrade
5. Verify pipelines running
6. Monitor for issues

### Health Checks

Configure health checks:

```yaml
monitoring:
  health:
    enabled: true
    port: 8081
    path: /health
```

**Health endpoints:**
- `/health` - Overall health
- `/health/ready` - Ready to accept traffic
- `/health/live` - Application is running

**Kubernetes liveness probe:**
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8081
  initialDelaySeconds: 30
  periodSeconds: 10
```

## Best Practices

1. **Monitor everything** - Metrics, logs, traces
2. **Use checkpoints** - Enable for production pipelines
3. **Plan capacity** - Size appropriately for workload
4. **Test upgrades** - Always test in staging first
5. **Secure by default** - Enable authentication and TLS
6. **Automate operations** - Use infrastructure as code
7. **Document runbooks** - Create incident response plans
8. **Regular backups** - Back up checkpoints and state

## Next Steps

- Review [Security Best Practices](security-guide.md)
- Learn about [High Availability](ha-guide.md)
- Explore [Advanced Operations](advanced-ops.md)
