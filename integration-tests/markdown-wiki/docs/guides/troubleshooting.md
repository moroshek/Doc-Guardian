# Troubleshooting Guide

Solutions to common DataFlow issues.

**Last Updated:** 2024-11-28

## Quick Diagnostics

First steps when something goes wrong:

```bash
# Check service status
dataflow status

# View recent logs
dataflow logs --tail 100

# Check resource usage
dataflow metrics

# Validate configuration
dataflow config validate
```

## Common Issues

### Pipeline Won't Start

**Symptom:** Pipeline fails to start with error message.

**Common Causes:**

#### 1. Configuration Error
```
Error: Invalid configuration: runtime.workers must be positive
```

**Solution:**
```bash
# Validate config
dataflow config validate dataflow.yaml

# Check syntax
yamllint dataflow.yaml
```

#### 2. Port Already in Use
```
Error: Address already in use: 0.0.0.0:8080
```

**Solution:**
```bash
# Find process using port
lsof -i :8080

# Kill process or change port in config
dataflow:
  port: 8081
```

#### 3. Missing Dependencies
```
Error: Cannot connect to Kafka: kafka1:9092
```

**Solution:**
```bash
# Check connectivity
nc -zv kafka1 9092

# Verify DNS resolution
nslookup kafka1

# Check credentials
echo $KAFKA_USER $KAFKA_PASS
```

### High Memory Usage

**Symptom:** Pipeline consumes excessive memory or crashes with OOM.

**Diagnosis:**
```bash
# Check memory metrics
curl http://localhost:9090/metrics | grep memory

# Analyze heap dump
dataflow debug heap-dump --output heap.hprof
```

**Solutions:**

#### 1. Increase Memory Limit
```yaml
runtime:
  memory: 32GB  # Increase from 16GB
```

#### 2. Reduce Batch Sizes
```yaml
runtime:
  performance:
    batch_size: 500  # Reduce from 1000
    buffer_size: 5000  # Reduce from 10000
```

#### 3. Enable Spilling to Disk
```yaml
runtime:
  spill:
    enabled: true
    directory: /tmp/dataflow-spill
    threshold: 0.8  # Spill when 80% memory used
```

#### 4. Optimize Checkpoints
```yaml
runtime:
  checkpoint_compression: true
  checkpoint_async: true
```

### High Latency

**Symptom:** Events take too long to process.

**Diagnosis:**
```bash
# Check latency metrics
curl http://localhost:9090/metrics | grep latency

# View traces
dataflow trace --pipeline my-pipeline
```

**Solutions:**

#### 1. Increase Parallelism
```yaml
runtime:
  workers: 16  # Increase from 8
```

#### 2. Optimize Transformations
```python
# Before (inefficient)
data.map(slow_function)

# After (batched)
data.batch(1000).map(batch_process)
```

#### 3. Tune Kafka Settings
```yaml
sources:
  kafka:
    fetch_min_bytes: 1MB  # Fetch more data per request
    max_poll_records: 1000  # Process more per poll
```

#### 4. Add Caching
```python
# Cache expensive lookups
reference_data = pipeline.read(DatabaseSource(...)).cache()
stream.join(reference_data, on="id")
```

### Connection Timeouts

**Symptom:** "Connection timeout" or "Connection refused" errors.

**Solutions:**

#### 1. Increase Timeouts
```yaml
sources:
  kafka:
    request_timeout_ms: 60000  # 60 seconds
    session_timeout_ms: 30000
```

#### 2. Add Retries
```yaml
runtime:
  retry:
    max_attempts: 5
    backoff: exponential
    initial_delay: 1s
```

#### 3. Check Network
```bash
# Test connectivity
telnet kafka1 9092

# Check firewall rules
iptables -L

# Verify security groups (cloud)
aws ec2 describe-security-groups
```

### Data Loss

**Symptom:** Missing events in output.

**Diagnosis:**
```bash
# Check error metrics
curl http://localhost:9090/metrics | grep failed

# View error logs
dataflow logs --level error

# Check dead letter queue
ls /var/dataflow/dlq/
```

**Solutions:**

#### 1. Enable Checkpointing
```yaml
runtime:
  checkpoint_interval: 60s
  checkpoint_dir: /var/dataflow/checkpoints
```

#### 2. Increase Kafka Retention
```yaml
sources:
  kafka:
    auto_commit_enable: false  # Manual commit
    enable_auto_commit: false
```

#### 3. Add Error Handling
```python
from dataflow import DeadLetterQueue

dlq = DeadLetterQueue(FileSink("./errors"))
data.map(risky_transform, on_error=dlq)
```

### Checkpoint Failures

**Symptom:** "Checkpoint failed" errors.

**Solutions:**

#### 1. Check Disk Space
```bash
df -h /var/dataflow/checkpoints
```

#### 2. Verify Permissions
```bash
ls -ld /var/dataflow/checkpoints
chown dataflow:dataflow /var/dataflow/checkpoints
```

#### 3. Use Compression
```yaml
runtime:
  checkpoint_compression: true
```

#### 4. Increase Interval
```yaml
runtime:
  checkpoint_interval: 120s  # Less frequent
```

### Kafka Consumer Lag

**Symptom:** Consumer group falling behind.

**Diagnosis:**
```bash
# Check lag
kafka-consumer-groups.sh \
  --bootstrap-server kafka1:9092 \
  --group dataflow-consumers \
  --describe
```

**Solutions:**

#### 1. Scale Consumers
```yaml
sources:
  kafka:
    consumer_instances: 8  # Match partition count
```

#### 2. Increase Throughput
```yaml
sources:
  kafka:
    max_poll_records: 1000
    fetch_max_bytes: 10MB
```

#### 3. Optimize Processing
```python
# Parallel processing
data.repartition(16).map(process_event)
```

### Authentication Errors

**Symptom:** "Unauthorized" or "Authentication failed" errors.

**Solutions:**

#### 1. Verify Credentials
```bash
# Check environment variables
echo $KAFKA_USER
echo $KAFKA_PASS

# Test authentication
kafka-console-consumer.sh \
  --bootstrap-server kafka1:9092 \
  --consumer-property security.protocol=SASL_SSL \
  --consumer-property sasl.username=$KAFKA_USER \
  --consumer-property sasl.password=$KAFKA_PASS \
  --topic test
```

#### 2. Check Token Expiry
```yaml
security:
  authentication:
    oauth2:
      refresh_before_expiry: 300s  # Refresh 5 min early
```

#### 3. Verify Certificates
```bash
# Check certificate validity
openssl x509 -in cert.pem -text -noout

# Verify CA chain
openssl verify -CAfile ca.pem cert.pem
```

## Performance Issues

### Slow Startup

**Causes:**
- Large state recovery
- Many partitions
- Network latency

**Solutions:**
```yaml
runtime:
  lazy_initialization: true
  parallel_initialization: true

sources:
  kafka:
    fetch_initial_offset: earliest  # Or 'latest' to skip old data
```

### High CPU Usage

**Diagnosis:**
```bash
# Check CPU metrics
top -p $(pgrep dataflow)

# Profile CPU usage
dataflow debug profile --duration 60s
```

**Solutions:**
```yaml
# Reduce worker count
runtime:
  workers: 8  # If I/O bound

# Add backpressure
runtime:
  performance:
    backpressure_threshold: 0.7
```

### Garbage Collection Issues

**Symptoms:** Long GC pauses affecting latency.

**Solutions:**
```yaml
runtime:
  jvm_options:
    - "-XX:+UseG1GC"
    - "-XX:MaxGCPauseMillis=200"
    - "-XX:InitiatingHeapOccupancyPercent=45"
    - "-XX:+PrintGCDetails"
    - "-Xlog:gc*:file=/var/log/dataflow/gc.log"
```

## Monitoring Issues

### Metrics Not Appearing

**Solutions:**

#### 1. Check Metrics Endpoint
```bash
curl http://localhost:9090/metrics
```

#### 2. Verify Configuration
```yaml
monitoring:
  metrics:
    enabled: true
    port: 9090
```

#### 3. Check Prometheus Config
```yaml
scrape_configs:
  - job_name: 'dataflow'
    static_configs:
      - targets: ['localhost:9090']
```

### Logs Not Appearing

**Solutions:**

#### 1. Check Log Level
```yaml
monitoring:
  logging:
    level: info  # Not 'silent'
```

#### 2. Verify Output Path
```bash
ls -l /var/log/dataflow/
tail -f /var/log/dataflow/dataflow.log
```

#### 3. Check Permissions
```bash
chown dataflow:dataflow /var/log/dataflow/
```

## Recovery Procedures

### Recover from Checkpoint

```bash
# Stop pipeline
dataflow stop my-pipeline

# List checkpoints
ls /var/dataflow/checkpoints/my-pipeline/

# Restore from specific checkpoint
dataflow start my-pipeline \
  --checkpoint /var/dataflow/checkpoints/my-pipeline/checkpoint-123
```

### Reset Pipeline State

```bash
# Stop pipeline
dataflow stop my-pipeline

# Clear state
rm -rf /var/dataflow/checkpoints/my-pipeline/

# Reset Kafka offsets
kafka-consumer-groups.sh \
  --bootstrap-server kafka1:9092 \
  --group dataflow-consumers \
  --topic my-topic \
  --reset-offsets --to-earliest \
  --execute

# Restart pipeline
dataflow start my-pipeline
```

### Recover from Data Corruption

```bash
# Export good data
dataflow export --pipeline my-pipeline --before 2025-01-10T00:00:00

# Clean corrupted data
dataflow clean --pipeline my-pipeline

# Reimport data
dataflow import --pipeline my-pipeline --data export.json
```

## Debug Mode

Enable debug mode for detailed diagnostics:

```yaml
monitoring:
  logging:
    level: debug

debug:
    enabled: true
    profiling: true
    heap_dumps: true
```

Run with debug flags:
```bash
dataflow run --debug --profile my-pipeline.py
```

## Getting Help

### Collect Debug Information

```bash
# Generate debug bundle
dataflow debug bundle --output debug.tar.gz

# Bundle includes:
# - Configuration
# - Recent logs
# - Metrics snapshot
# - Stack traces
# - Resource usage
```

### Check Documentation

- [User Guide](user-guide.md) - Pipeline development
- [Admin Guide](admin-guide.md) - Operations and deployment
- [Configuration Guide](../getting-started/configuration.md) - Config options
- [API Reference](../reference/api.md) - API documentation

### Community Support

- **Discord**: [discord.gg/dataflow](https://discord.gg/dataflow)
- **GitHub Issues**: [github.com/dataflow/dataflow/issues](https://github.com/dataflow/dataflow/issues)
- **Stack Overflow**: Tag questions with `dataflow`
- **Forum**: [forum.dataflow.io](https://forum.dataflow.io)

### Commercial Support

For enterprise support:
- Email: support@dataflow.io
- SLA: Response within 4 hours (critical issues)
- Includes: Architecture review, performance tuning, custom development

## Known Issues

### Issue #1234: Memory leak in windowing
**Affects**: Versions 2.3.0-2.3.2
**Workaround**: Upgrade to 2.3.3+
**Fix**: Included in 2.3.3

### Issue #5678: Kafka rebalancing storms
**Affects**: All versions with >100 partitions
**Workaround**: Increase `session.timeout.ms` to 60000
**Status**: Fix in progress (ETA: 2.5.0)

## Best Practices

1. **Enable checkpointing** - Always use checkpoints in production
2. **Monitor everything** - Set up metrics, logs, and alerts
3. **Test configuration** - Validate config before deploying
4. **Start small** - Test with small data volumes first
5. **Use retries** - Configure retry logic for transient failures
6. **Plan capacity** - Size infrastructure appropriately
7. **Keep logs** - Retain logs for at least 30 days
8. **Regular backups** - Back up checkpoints daily

## Diagnostic Commands

```bash
# System info
dataflow info

# Health check
dataflow health

# List pipelines
dataflow list

# Pipeline status
dataflow status my-pipeline

# Recent errors
dataflow logs --level error --tail 50

# Metrics summary
dataflow metrics summary

# Configuration dump
dataflow config dump

# Version info
dataflow version
```
