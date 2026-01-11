# Configuration Guide

Learn how to configure DataFlow for your environment.

**Last Updated:** 2024-10-20

## Configuration Files

DataFlow looks for configuration in these locations (in order):
1. `./dataflow.yaml` (current directory)
2. `~/.dataflow/config.yaml` (user home)
3. `/etc/dataflow/config.yaml` (system-wide)

## Basic Configuration

Minimal `dataflow.yaml`:

```yaml
runtime:
  workers: 4
  memory: 4GB
```

This configures 4 worker threads with 4GB memory limit.

## Runtime Options

### Workers

Control parallelism:

```yaml
runtime:
  workers: 8  # Number of worker threads
  worker_memory: 512MB  # Memory per worker
```

More workers = better throughput for parallel operations.

### Checkpointing

Enable fault tolerance:

```yaml
runtime:
  checkpoint_interval: 60s
  checkpoint_dir: /var/dataflow/checkpoints
  checkpoint_compression: true
```

Checkpoints allow recovery from failures.

### Networking

Configure network settings:

```yaml
runtime:
  bind_address: 0.0.0.0
  port: 8080
  tls:
    enabled: true
    cert: /path/to/cert.pem
    key: /path/to/key.pem
```

## Source Configuration

### Kafka Sources

```yaml
sources:
  kafka:
    bootstrap_servers:
      - kafka1:9092
      - kafka2:9092
    security_protocol: SASL_SSL
    sasl_mechanism: PLAIN
    sasl_username: ${KAFKA_USER}
    sasl_password: ${KAFKA_PASS}
    consumer_group: dataflow-consumers
```

### Database Sources

```yaml
sources:
  postgres:
    connection_string: postgresql://user:pass@localhost/db
    pool_size: 10
    timeout: 30s

  mysql:
    host: localhost
    port: 3306
    database: mydb
    user: ${DB_USER}
    password: ${DB_PASS}
```

### File Sources

```yaml
sources:
  files:
    base_path: /data
    glob_patterns:
      - "*.csv"
      - "*.json"
    watch_mode: true  # Monitor for new files
```

## Sink Configuration

### Kafka Sinks

```yaml
sinks:
  kafka:
    bootstrap_servers: kafka1:9092
    compression: gzip
    acks: all  # Wait for all replicas
    batch_size: 16384
```

### Database Sinks

```yaml
sinks:
  postgres:
    connection_string: postgresql://localhost/analytics
    batch_size: 1000
    flush_interval: 5s
```

### File Sinks

```yaml
sinks:
  files:
    base_path: /output
    format: parquet
    compression: snappy
    rotation:
      size: 100MB
      time: 1h
```

## Monitoring

Configure metrics and logging:

```yaml
monitoring:
  metrics:
    enabled: true
    port: 9090
    path: /metrics

  logging:
    level: info
    format: json
    output: /var/log/dataflow.log

  tracing:
    enabled: true
    jaeger_endpoint: http://jaeger:14268/api/traces
```

## Environment Variables

Use environment variables for sensitive data:

```yaml
sources:
  kafka:
    bootstrap_servers: ${KAFKA_BROKERS}
    sasl_username: ${KAFKA_USER}
    sasl_password: ${KAFKA_PASS}
```

Set in your environment:
```bash
export KAFKA_BROKERS=kafka1:9092,kafka2:9092
export KAFKA_USER=myuser
export KAFKA_PASS=secret123
```

## Profiles

Use different configs for different environments:

```yaml
# dataflow.yaml
runtime:
  workers: 4

---
# Profile: dev
runtime:
  workers: 1
  log_level: debug

---
# Profile: prod
runtime:
  workers: 16
  checkpoint_interval: 30s
  monitoring:
    enabled: true
```

Activate a profile:
```bash
dataflow run --profile prod my_pipeline.py
```

## Advanced Options

### Memory Management

```yaml
runtime:
  memory:
    heap_size: 4GB
    off_heap_size: 2GB
    gc_strategy: g1gc
```

### Performance Tuning

```yaml
runtime:
  performance:
    batch_size: 1000
    buffer_size: 10000
    backpressure_threshold: 0.8
    prefetch_count: 100
```

### Security

```yaml
security:
  authentication:
    enabled: true
    method: oauth2
    oauth2:
      issuer_url: https://auth.example.com
      client_id: dataflow

  authorization:
    enabled: true
    policy_file: /etc/dataflow/policies.yaml
```

## Configuration Validation

Validate your config before running:

```bash
dataflow config validate dataflow.yaml
```

## Configuration Reference

For complete config options, see:
- [Config Reference](../reference/config.md)
- [Environment Variables](../reference/environment.md)
- [Security Configuration](../guides/security.md)

## Examples

### Development Config
```yaml
runtime:
  workers: 1
  log_level: debug
  checkpoint_interval: 5s

monitoring:
  metrics:
    enabled: false
```

### Production Config
```yaml
runtime:
  workers: 16
  memory: 32GB
  checkpoint_interval: 60s
  checkpoint_compression: true

monitoring:
  metrics:
    enabled: true
  tracing:
    enabled: true

security:
  authentication:
    enabled: true
```

## Next Steps

- Learn about [pipeline development](../guides/user-guide.md)
- Set up [monitoring and alerting](../guides/admin-guide.md#monitoring)
- Explore [deployment patterns](../guides/deployment.md)
