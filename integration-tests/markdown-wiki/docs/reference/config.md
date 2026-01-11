# Configuration Reference

Complete reference for DataFlow configuration options.

**Last Updated:** 2025-01-10

## Configuration File Format

DataFlow uses YAML configuration files:

```yaml
# dataflow.yaml
project:
  name: my-project
  version: 1.0.0

runtime:
  workers: 8
  memory: 16GB

sources:
  kafka:
    bootstrap_servers: localhost:9092

sinks:
  postgres:
    connection_string: postgresql://localhost/db
```

## Configuration Locations

DataFlow searches for config files in this order:

1. Path specified via `--config` flag
2. `./dataflow.yaml` (current directory)
3. `~/.dataflow/config.yaml` (user home)
4. `/etc/dataflow/config.yaml` (system-wide)

## Runtime Configuration

### runtime

Core runtime settings.

```yaml
runtime:
  workers: 8
  memory: 16GB
  worker_memory: 2GB

  # Checkpointing
  checkpoint_interval: 60s
  checkpoint_dir: /var/dataflow/checkpoints
  checkpoint_compression: true
  checkpoint_async: true

  # Networking
  bind_address: 0.0.0.0
  port: 8080

  # Performance
  performance:
    batch_size: 1000
    buffer_size: 10000
    prefetch_count: 100
    backpressure_threshold: 0.8

  # Memory management
  memory_mode: balanced  # conservative, balanced, aggressive
  spill:
    enabled: true
    directory: /tmp/dataflow-spill
    threshold: 0.8
```

**Options:**

#### workers
- Type: integer
- Default: Number of CPU cores
- Description: Number of worker threads

#### memory
- Type: string
- Default: "4GB"
- Format: Number + unit (KB, MB, GB, TB)
- Description: Total memory limit

#### checkpoint_interval
- Type: duration
- Default: "60s"
- Format: Number + unit (s, m, h)
- Description: Checkpoint frequency

## Source Configuration

### sources.kafka

Kafka source settings.

```yaml
sources:
  kafka:
    bootstrap_servers: kafka1:9092,kafka2:9092

    # Consumer settings
    consumer_group: dataflow-consumers
    auto_offset_reset: earliest  # earliest, latest, none
    enable_auto_commit: true
    auto_commit_interval_ms: 5000

    # Security
    security_protocol: SASL_SSL  # PLAINTEXT, SASL_PLAINTEXT, SSL, SASL_SSL
    sasl_mechanism: PLAIN  # PLAIN, SCRAM-SHA-256, SCRAM-SHA-512
    sasl_username: ${KAFKA_USER}
    sasl_password: ${KAFKA_PASS}

    # SSL/TLS
    ssl_ca_location: /path/to/ca.pem
    ssl_cert_location: /path/to/cert.pem
    ssl_key_location: /path/to/key.pem

    # Performance
    fetch_min_bytes: 1MB
    fetch_max_wait_ms: 500
    max_poll_records: 1000
    max_partition_fetch_bytes: 10MB

    # Timeouts
    request_timeout_ms: 30000
    session_timeout_ms: 10000
```

### sources.postgres

PostgreSQL source settings.

```yaml
sources:
  postgres:
    connection_string: postgresql://user:pass@host:5432/db

    # Connection pool
    pool_size: 10
    max_overflow: 20
    pool_timeout: 30
    pool_recycle: 3600

    # Query settings
    fetch_size: 1000
    statement_timeout: 60s

    # SSL
    sslmode: require  # disable, allow, prefer, require, verify-ca, verify-full
    sslcert: /path/to/cert.pem
    sslkey: /path/to/key.pem
    sslrootcert: /path/to/ca.pem
```

### sources.files

File source settings.

```yaml
sources:
  files:
    base_path: /data
    glob_patterns:
      - "*.csv"
      - "*.json"
      - "*.parquet"

    # Watching
    watch_mode: true
    watch_interval: 10s

    # Parsing
    encoding: utf-8
    compression: auto  # auto, gzip, bzip2, xz, none

    # CSV-specific
    csv:
      delimiter: ","
      quote_char: "\""
      escape_char: "\\"
      header: true
```

## Sink Configuration

### sinks.kafka

Kafka sink settings.

```yaml
sinks:
  kafka:
    bootstrap_servers: kafka1:9092

    # Producer settings
    acks: all  # 0, 1, all
    compression_type: gzip  # none, gzip, snappy, lz4, zstd
    batch_size: 16384
    linger_ms: 10
    buffer_memory: 32MB

    # Retries
    retries: 3
    retry_backoff_ms: 100
    max_in_flight_requests: 5

    # Timeouts
    request_timeout_ms: 30000
    delivery_timeout_ms: 120000

    # Security (same as sources.kafka)
    security_protocol: SASL_SSL
    sasl_mechanism: PLAIN
    sasl_username: ${KAFKA_USER}
    sasl_password: ${KAFKA_PASS}
```

### sinks.postgres

PostgreSQL sink settings.

```yaml
sinks:
  postgres:
    connection_string: postgresql://user:pass@host:5432/db

    # Write settings
    batch_size: 1000
    flush_interval: 5s
    mode: append  # append, overwrite, upsert

    # Upsert settings (for mode: upsert)
    upsert:
      conflict_columns:
        - id
      update_columns:
        - value
        - updated_at

    # Connection pool (same as sources.postgres)
    pool_size: 10
```

### sinks.files

File sink settings.

```yaml
sinks:
  files:
    base_path: /output

    # Format
    format: parquet  # parquet, json, csv, avro
    compression: snappy  # none, snappy, gzip, lz4, zstd

    # Partitioning
    partition_by:
      - year
      - month
      - day

    # Rotation
    rotation:
      size: 100MB
      time: 1h
      count: 1000

    # Parquet-specific
    parquet:
      row_group_size: 128MB
      page_size: 1MB
      compression_level: 5
```

## Monitoring Configuration

### monitoring.metrics

Metrics configuration.

```yaml
monitoring:
  metrics:
    enabled: true
    port: 9090
    path: /metrics

    # Prometheus
    prometheus:
      pushgateway: http://pushgateway:9091
      push_interval: 10s
      job_name: dataflow

    # Custom metrics
    custom:
      - name: business_metric
        type: counter
        help: "Custom business metric"
```

### monitoring.logging

Logging configuration.

```yaml
monitoring:
  logging:
    level: info  # debug, info, warn, error, fatal
    format: json  # text, json
    output: /var/log/dataflow/dataflow.log

    # Rotation
    rotation:
      max_size: 100MB
      max_age: 30d
      max_backups: 10
      compress: true

    # Fields
    include_fields:
      - timestamp
      - level
      - message
      - pipeline
      - worker
      - trace_id
```

### monitoring.tracing

Distributed tracing configuration.

```yaml
monitoring:
  tracing:
    enabled: true
    backend: jaeger  # jaeger, zipkin, otlp

    # Jaeger
    jaeger:
      endpoint: http://jaeger:14268/api/traces
      agent_host: localhost
      agent_port: 6831
      sample_rate: 0.1

    # Zipkin
    zipkin:
      endpoint: http://zipkin:9411/api/v2/spans

    # OTLP
    otlp:
      endpoint: http://otel-collector:4318
      protocol: http  # http, grpc
```

### monitoring.health

Health check configuration.

```yaml
monitoring:
  health:
    enabled: true
    port: 8081
    path: /health

    # Checks
    checks:
      - name: disk_space
        threshold: 90%
      - name: memory
        threshold: 90%
      - name: cpu
        threshold: 80%
```

## Security Configuration

### security.authentication

Authentication settings.

```yaml
security:
  authentication:
    enabled: true
    method: oauth2  # basic, oauth2, jwt, mtls

    # OAuth2
    oauth2:
      issuer_url: https://auth.example.com
      client_id: dataflow
      client_secret: ${OAUTH_SECRET}
      scopes:
        - openid
        - profile

    # JWT
    jwt:
      secret: ${JWT_SECRET}
      algorithm: HS256  # HS256, RS256
      issuer: dataflow
      audience: api
      expiry: 1h

    # Basic auth
    basic:
      users:
        - username: admin
          password_hash: $2b$12$...
```

### security.authorization

Authorization settings.

```yaml
security:
  authorization:
    enabled: true
    policy_file: /etc/dataflow/policies.yaml

    # RBAC
    rbac:
      roles:
        - name: admin
          permissions: ["*"]
        - name: user
          permissions:
            - pipeline:read
            - pipeline:create
        - name: viewer
          permissions:
            - pipeline:read
```

### security.tls

TLS/SSL settings.

```yaml
security:
  tls:
    enabled: true
    cert: /etc/dataflow/certs/server.crt
    key: /etc/dataflow/certs/server.key
    ca: /etc/dataflow/certs/ca.crt

    # Client verification
    verify_client: true
    client_ca: /etc/dataflow/certs/client-ca.crt

    # Cipher suites
    cipher_suites:
      - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
      - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384

    # TLS version
    min_version: "1.2"
    max_version: "1.3"
```

## Advanced Configuration

### disaster_recovery

Disaster recovery settings.

```yaml
runtime:
  disaster_recovery:
    enabled: true
    backup_interval: 1h
    backup_location: s3://backups/dataflow
    retention_days: 30

    # S3 settings
    s3:
      region: us-east-1
      access_key_id: ${AWS_ACCESS_KEY}
      secret_access_key: ${AWS_SECRET_KEY}
```

### jvm_options

JVM tuning (for JVM-based runtimes).

```yaml
runtime:
  jvm_options:
    - "-Xms8g"
    - "-Xmx16g"
    - "-XX:+UseG1GC"
    - "-XX:MaxGCPauseMillis=200"
    - "-XX:InitiatingHeapOccupancyPercent=45"
    - "-XX:+HeapDumpOnOutOfMemoryError"
    - "-XX:HeapDumpPath=/var/log/dataflow/heap-dump.hprof"
```

### retry

Global retry configuration.

```yaml
runtime:
  retry:
    max_attempts: 3
    backoff: exponential  # fixed, linear, exponential
    initial_delay: 1s
    max_delay: 60s
    multiplier: 2.0
    jitter: true
```

## Environment Variables

All config values can be set via environment variables:

```bash
# Format: DATAFLOW_<SECTION>_<KEY>
export DATAFLOW_RUNTIME_WORKERS=16
export DATAFLOW_RUNTIME_MEMORY=32GB
export DATAFLOW_MONITORING_LOGGING_LEVEL=debug

# Nested sections use underscores
export DATAFLOW_SOURCES_KAFKA_BOOTSTRAP_SERVERS=kafka:9092
export DATAFLOW_SINKS_POSTGRES_CONNECTION_STRING=postgresql://localhost/db
```

**Secret values:**
```bash
# Use ${VAR} in config, set in environment
export KAFKA_USER=myuser
export KAFKA_PASS=secret123
export OAUTH_SECRET=oauth-secret
```

## Configuration Profiles

Use profiles for different environments:

```yaml
# dataflow.yaml - defaults
runtime:
  workers: 4
  memory: 8GB

---
# Profile: dev
runtime:
  workers: 1
  memory: 2GB
  checkpoint_interval: 5s
monitoring:
  logging:
    level: debug

---
# Profile: prod
runtime:
  workers: 16
  memory: 64GB
  checkpoint_interval: 60s
monitoring:
  logging:
    level: info
  metrics:
    enabled: true
security:
  authentication:
    enabled: true
```

Activate profile:
```bash
dataflow run --profile prod my_pipeline.py
```

## Validation

Validate configuration:

```bash
dataflow config validate dataflow.yaml
```

Shows:
- Syntax errors
- Invalid values
- Missing required fields
- Deprecated options

## Examples

### Development Configuration

Minimal config for local development:

```yaml
runtime:
  workers: 2
  memory: 4GB
  checkpoint_dir: ./checkpoints

monitoring:
  logging:
    level: debug
    format: text
```

### Production Configuration

Full production config:

```yaml
runtime:
  workers: 16
  memory: 64GB
  checkpoint_interval: 60s
  checkpoint_dir: /var/dataflow/checkpoints
  checkpoint_compression: true
  checkpoint_async: true

sources:
  kafka:
    bootstrap_servers: ${KAFKA_BROKERS}
    security_protocol: SASL_SSL
    sasl_mechanism: PLAIN
    sasl_username: ${KAFKA_USER}
    sasl_password: ${KAFKA_PASS}

monitoring:
  metrics:
    enabled: true
    prometheus:
      pushgateway: ${PROMETHEUS_PUSHGATEWAY}

  logging:
    level: info
    format: json
    output: /var/log/dataflow/dataflow.log
    rotation:
      max_size: 100MB
      max_backups: 30

  tracing:
    enabled: true
    backend: jaeger
    jaeger:
      endpoint: ${JAEGER_ENDPOINT}

security:
  authentication:
    enabled: true
    method: oauth2
    oauth2:
      issuer_url: ${OAUTH_ISSUER}
      client_id: ${OAUTH_CLIENT_ID}
      client_secret: ${OAUTH_SECRET}

  tls:
    enabled: true
    cert: /etc/dataflow/certs/server.crt
    key: /etc/dataflow/certs/server.key
```

## See Also

- [User Guide](../guides/user-guide.md) - Using DataFlow
- [Admin Guide](../guides/admin-guide.md) - Operations
- [CLI Reference](cli.md) - Command-line tools
- [Security Guide](../guides/security-config.md) - Security best practices
