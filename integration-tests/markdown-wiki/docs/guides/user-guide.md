# User Guide

Complete guide to building data pipelines with DataFlow.

**Last Updated:** 2025-01-08

## Table of Contents

- [Pipeline Basics](#pipeline-basics)
- [Sources and Sinks](#sources-and-sinks)
- [Transformations](#transformations)
- [Windowing](#windowing)
- [State Management](#state-management)
- [Error Handling](#error-handling)

## Pipeline Basics

A DataFlow pipeline consists of three parts:
1. **Sources** - Where data comes from
2. **Transformations** - How data is processed
3. **Sinks** - Where data goes

Basic pipeline structure:

```python
from dataflow import Pipeline

# Create pipeline
pipeline = Pipeline("my-pipeline")

# Read data (source)
data = pipeline.read(Source(...))

# Transform data
processed = data.map(transform_fn)

# Write data (sink)
processed.write(Sink(...))

# Execute
pipeline.run()
```

## Sources and Sinks

DataFlow provides many built-in connectors. See the [Connector Guide](connectors.md) for full details.

### Common Sources

**File Sources**
```python
from dataflow import TextSource, JsonSource, ParquetSource

# Text files
pipeline.read(TextSource("./data/*.txt"))

# JSON files
pipeline.read(JsonSource("./data/*.json"))

# Parquet files
pipeline.read(ParquetSource("./data/*.parquet"))
```

**Streaming Sources**
```python
from dataflow import KafkaSource, WebSocketSource

# Kafka
pipeline.read(KafkaSource(
    topic="events",
    bootstrap_servers="localhost:9092"
))

# WebSocket
pipeline.read(WebSocketSource("ws://localhost:8080"))
```

**Database Sources**
```python
from dataflow import PostgresSource, MySQLSource

# PostgreSQL
pipeline.read(PostgresSource(
    query="SELECT * FROM events WHERE created > NOW() - INTERVAL '1 hour'",
    connection_string="postgresql://localhost/mydb"
))
```

### Common Sinks

**File Sinks**
```python
from dataflow import FileSink

data.write(FileSink(
    path="./output",
    format="parquet",
    partition_by=["date", "hour"]
))
```

**Streaming Sinks**
```python
from dataflow import KafkaSink

data.write(KafkaSink(
    topic="processed-events",
    bootstrap_servers="localhost:9092"
))
```

**Database Sinks**
```python
from dataflow import DatabaseSink

data.write(DatabaseSink(
    table="analytics",
    connection_string="postgresql://localhost/warehouse"
))
```

## Transformations

Transform data as it flows through your pipeline.

### Map
Transform each element:

```python
# Simple transformation
data.map(lambda x: x.upper())

# With function
def parse_log(line):
    timestamp, level, message = line.split("|")
    return {
        "timestamp": timestamp,
        "level": level,
        "message": message
    }

logs.map(parse_log)
```

### Filter
Keep only elements that match a condition:

```python
# Simple filter
data.filter(lambda x: x > 100)

# Complex filter
def is_error(log):
    return log["level"] == "ERROR"

logs.filter(is_error)
```

### FlatMap
Transform each element into multiple elements:

```python
# Split text into words
lines.flat_map(lambda line: line.split())

# Parse nested data
data.flat_map(lambda x: x["items"])
```

### Reduce
Combine elements:

```python
# Sum values
numbers.reduce(lambda a, b: a + b)

# Custom reduction
def merge_dicts(a, b):
    result = a.copy()
    result.update(b)
    return result

dicts.reduce(merge_dicts)
```

## Windowing

Group streaming data by time windows.

### Tumbling Windows
Non-overlapping fixed-size windows:

```python
from dataflow import Window

# 5-minute tumbling windows
events.window(Window.tumbling(minutes=5))
```

### Sliding Windows
Overlapping windows:

```python
# 10-minute windows, sliding every 5 minutes
events.window(Window.sliding(
    size={"minutes": 10},
    slide={"minutes": 5}
))
```

### Session Windows
Windows based on activity gaps:

```python
# Group events with <5 min gap between them
events.window(Window.session(gap={"minutes": 5}))
```

### Aggregations
Compute statistics over windows:

```python
from dataflow import Aggregate

# Count events per window
windowed.aggregate(Aggregate.count())

# Sum values
windowed.aggregate(Aggregate.sum("amount"))

# Average
windowed.aggregate(Aggregate.avg("value"))

# Multiple aggregations
windowed.aggregate([
    Aggregate.count(),
    Aggregate.sum("amount"),
    Aggregate.max("value")
])
```

## State Management

Maintain state across pipeline executions.

### Key-Value State

```python
from dataflow import State

# Create stateful transformation
def count_by_user(state: State, event):
    user = event["user_id"]
    count = state.get(user, default=0)
    state.put(user, count + 1)
    return {"user": user, "count": count + 1}

events.map_with_state(count_by_user)
```

### List State

```python
def collect_events(state: State, event):
    events = state.get("events", default=[])
    events.append(event)
    state.put("events", events)
    return events

stream.map_with_state(collect_events)
```

### State Persistence

Enable checkpointing to persist state:

```yaml
# dataflow.yaml
runtime:
  checkpoint_interval: 60s
  checkpoint_dir: /var/dataflow/checkpoints
```

See [Configuration Guide](../getting-started/configuration.md) for checkpoint options.

## Error Handling

Handle errors gracefully in your pipelines.

### Try-Catch Pattern

```python
def safe_transform(element):
    try:
        return transform(element)
    except Exception as e:
        return {"error": str(e), "element": element}

data.map(safe_transform)
```

### Dead Letter Queue

Route failed elements to a separate sink:

```python
from dataflow import DeadLetterQueue

# Create DLQ
dlq = DeadLetterQueue(FileSink("./errors"))

# Process with DLQ
data.map(risky_transform, on_error=dlq)
```

### Retry Logic

```python
from dataflow import Retry

data.map(
    flaky_api_call,
    retry=Retry(
        max_attempts=3,
        backoff="exponential",
        initial_delay=1.0
    )
)
```

## Performance Tips

### Batch Operations
Process data in batches for better throughput:

```python
data.batch(size=1000).map(batch_process)
```

### Parallelism
Control parallel processing:

```python
# Increase parallelism
data.repartition(16).map(cpu_intensive_fn)

# Reduce parallelism for I/O bound operations
data.coalesce(1).write(Sink(...))
```

### Caching
Cache expensive computations:

```python
# Compute once, use many times
expensive_result = data.map(expensive_fn).cache()

expensive_result.filter(condition1).write(Sink1())
expensive_result.filter(condition2).write(Sink2())
```

## Testing Pipelines

Test your pipelines with sample data:

```python
from dataflow.testing import TestSource, TestSink

# Create test data
test_data = [1, 2, 3, 4, 5]

# Build pipeline
pipeline = Pipeline("test")
result = pipeline.read(TestSource(test_data)) \
    .map(lambda x: x * 2) \
    .collect()

# Verify results
assert result == [2, 4, 6, 8, 10]
```

See [Testing Guide](../contributing/testing.md) for comprehensive testing strategies.

## Monitoring Pipelines

Monitor pipeline health and performance:

```python
from dataflow import Metrics

pipeline = Pipeline("monitored", metrics=Metrics(
    port=9090,
    path="/metrics"
))
```

Access metrics at `http://localhost:9090/metrics`.

See [Admin Guide](admin-guide.md) for monitoring and operations.

## Common Patterns

### ETL Pipeline
```python
# Extract
data = pipeline.read(DatabaseSource(...))

# Transform
cleaned = data.map(clean_data) \
    .filter(validate_data) \
    .map(enrich_data)

# Load
cleaned.write(DataWarehouseSink(...))
```

### Stream Processing
```python
events = pipeline.read(KafkaSource(...))

# Real-time aggregation
metrics = events \
    .window(Window.tumbling(minutes=1)) \
    .aggregate(Aggregate.count())

metrics.write(MetricsSink(...))
```

### Data Enrichment
```python
stream = pipeline.read(KafkaSource("events"))
reference = pipeline.read(DatabaseSource("users"))

# Join streaming and batch data
enriched = stream.join(reference, on="user_id")
```

## Best Practices

1. **Start Small**: Test with small datasets first
2. **Use Type Hints**: Make code more maintainable
3. **Handle Errors**: Always consider failure cases
4. **Monitor**: Track metrics and logs
5. **Test**: Write tests for critical transformations
6. **Document**: Add comments for complex logic
7. **Version**: Use source control for pipeline code
8. **Checkpoint**: Enable checkpointing for production

## Next Steps

- Explore [advanced patterns](advanced-patterns.md)
- Learn about [deployment](../operations/deployment-guide.md)
- Read [performance tuning guide](performance.md)
- Check out [example pipelines](https://github.com/dataflow/examples)

## Need Help?

- Check [Troubleshooting Guide](troubleshooting.md)
- Ask on [Discord](https://discord.gg/dataflow)
- Browse [GitHub Discussions](https://github.com/dataflow/dataflow/discussions)
