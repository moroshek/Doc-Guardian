# API Reference

Complete API reference for DataFlow.

**Last Updated:** 2025-01-10

## Pipeline API

### Pipeline Class

Create and manage data processing pipelines.

```python
from dataflow import Pipeline

pipeline = Pipeline(
    name="my-pipeline",
    config="/path/to/config.yaml",
    metrics=True
)
```

**Constructor Parameters:**
- `name` (str): Pipeline name (required)
- `config` (str, optional): Path to config file
- `metrics` (bool, optional): Enable metrics collection (default: True)
- `checkpoint_dir` (str, optional): Checkpoint directory

**Methods:**

#### `read(source: Source) -> DataStream`
Read data from a source.

```python
data = pipeline.read(KafkaSource("topic"))
```

#### `run() -> None`
Execute the pipeline.

```python
pipeline.run()
```

#### `stop() -> None`
Stop the pipeline gracefully.

```python
pipeline.stop()
```

## DataStream API

### Transformations

#### `map(func: Callable) -> DataStream`
Transform each element.

```python
data.map(lambda x: x.upper())
data.map(parse_json)
```

**Parameters:**
- `func`: Function to apply to each element
- Returns: New DataStream

#### `filter(predicate: Callable) -> DataStream`
Filter elements.

```python
data.filter(lambda x: x > 0)
```

**Parameters:**
- `predicate`: Function returning bool
- Returns: New DataStream with filtered elements

#### `flat_map(func: Callable) -> DataStream`
Map each element to zero or more elements.

```python
lines.flat_map(lambda line: line.split())
```

#### `reduce(func: Callable) -> Any`
Reduce elements to single value.

```python
total = numbers.reduce(lambda a, b: a + b)
```

#### `batch(size: int) -> DataStream`
Group elements into batches.

```python
data.batch(size=1000)
```

**Parameters:**
- `size`: Batch size
- Returns: DataStream of lists

### Windowing

#### `window(window: Window) -> WindowedStream`
Apply windowing to stream.

```python
windowed = events.window(Window.tumbling(minutes=5))
```

See [Window API](#window-api) for window types.

#### `aggregate(agg: Aggregate) -> DataStream`
Aggregate windowed data.

```python
windowed.aggregate(Aggregate.count())
```

See [Aggregate API](#aggregate-api) for aggregation functions.

### Joining

#### `join(other: DataStream, on: str) -> DataStream`
Join two streams.

```python
enriched = stream.join(reference, on="user_id")
```

**Parameters:**
- `other`: DataStream to join with
- `on`: Key field name
- Returns: Joined DataStream

#### `left_join(other: DataStream, on: str) -> DataStream`
Left outer join.

```python
result = stream.left_join(reference, on="id")
```

### Output

#### `write(sink: Sink) -> None`
Write to a sink.

```python
data.write(KafkaSink("output-topic"))
```

#### `collect() -> List`
Collect all elements to a list (for testing).

```python
results = data.collect()
```

#### `print() -> None`
Print elements to console.

```python
data.print()
```

## Source API

### KafkaSource

Read from Apache Kafka topics.

```python
from dataflow import KafkaSource

source = KafkaSource(
    topic="events",
    bootstrap_servers="localhost:9092",
    consumer_group="dataflow",
    auto_offset_reset="earliest"
)
```

**Parameters:**
- `topic` (str): Kafka topic name
- `bootstrap_servers` (str): Kafka broker addresses
- `consumer_group` (str, optional): Consumer group ID
- `auto_offset_reset` (str, optional): 'earliest' or 'latest'
- `value_deserializer` (str, optional): 'json', 'avro', 'protobuf'

### FileSource

Read from files.

```python
from dataflow import TextSource, JsonSource, ParquetSource

# Text files
TextSource("./data/*.txt")

# JSON files
JsonSource("./data/*.json")

# Parquet files
ParquetSource("./data/*.parquet")
```

### DatabaseSource

Read from databases.

```python
from dataflow import DatabaseSource

source = DatabaseSource(
    query="SELECT * FROM events WHERE created > NOW() - INTERVAL '1 hour'",
    connection_string="postgresql://localhost/mydb",
    poll_interval=60  # seconds
)
```

**Supported databases:**
- PostgreSQL
- MySQL
- SQL Server
- Oracle
- MongoDB

### StreamSource

Read from streaming sources.

```python
from dataflow import WebSocketSource, HTTPSource

# WebSocket
WebSocketSource("ws://localhost:8080/events")

# HTTP streaming
HTTPSource("http://api.example.com/stream")
```

## Sink API

### KafkaSink

Write to Kafka topics.

```python
from dataflow import KafkaSink

sink = KafkaSink(
    topic="output",
    bootstrap_servers="localhost:9092",
    compression="gzip",
    acks="all"
)
```

**Parameters:**
- `topic` (str): Kafka topic
- `bootstrap_servers` (str): Broker addresses
- `compression` (str, optional): 'none', 'gzip', 'snappy', 'lz4'
- `acks` (str, optional): '0', '1', 'all'

### FileSink

Write to files.

```python
from dataflow import FileSink

sink = FileSink(
    path="./output",
    format="parquet",
    partition_by=["date", "hour"],
    compression="snappy"
)
```

**Supported formats:**
- `parquet` - Apache Parquet
- `json` - JSON lines
- `csv` - CSV
- `avro` - Apache Avro

### DatabaseSink

Write to databases.

```python
from dataflow import DatabaseSink

sink = DatabaseSink(
    table="analytics",
    connection_string="postgresql://localhost/warehouse",
    batch_size=1000,
    mode="append"  # or 'overwrite'
)
```

## Window API

### Window Types

#### Tumbling Windows
```python
from dataflow import Window

# Fixed-size non-overlapping windows
Window.tumbling(seconds=30)
Window.tumbling(minutes=5)
Window.tumbling(hours=1)
```

#### Sliding Windows
```python
# Overlapping windows
Window.sliding(
    size={"minutes": 10},
    slide={"minutes": 5}
)
```

#### Session Windows
```python
# Windows based on inactivity gap
Window.session(gap={"minutes": 5})
```

### Window Parameters

**Duration format:**
```python
{
    "seconds": 30,
    "minutes": 5,
    "hours": 1,
    "days": 1
}
```

## Aggregate API

### Aggregation Functions

```python
from dataflow import Aggregate

# Count
Aggregate.count()

# Sum
Aggregate.sum("field_name")

# Average
Aggregate.avg("field_name")

# Min/Max
Aggregate.min("field_name")
Aggregate.max("field_name")

# Multiple aggregations
windowed.aggregate([
    Aggregate.count(),
    Aggregate.sum("amount"),
    Aggregate.avg("value")
])
```

### Custom Aggregations

```python
def custom_agg(values):
    return {
        "count": len(values),
        "sum": sum(values),
        "custom": your_logic(values)
    }

windowed.aggregate(custom_agg)
```

## State API

### Stateful Transformations

```python
from dataflow import State

def count_events(state: State, event):
    key = event["user_id"]
    count = state.get(key, default=0)
    count += 1
    state.put(key, count)
    return {"user": key, "count": count}

stream.map_with_state(count_events)
```

**State Methods:**
- `get(key, default=None)` - Get value
- `put(key, value)` - Set value
- `delete(key)` - Remove value
- `exists(key)` - Check if key exists
- `keys()` - Get all keys
- `clear()` - Clear all state

## Error Handling API

### DeadLetterQueue

```python
from dataflow import DeadLetterQueue

dlq = DeadLetterQueue(
    sink=FileSink("./errors"),
    include_error=True,
    include_stack_trace=True
)

data.map(risky_transform, on_error=dlq)
```

### Retry Policy

```python
from dataflow import Retry

data.map(
    flaky_api_call,
    retry=Retry(
        max_attempts=3,
        backoff="exponential",
        initial_delay=1.0,
        max_delay=60.0
    )
)
```

**Backoff strategies:**
- `fixed` - Fixed delay
- `exponential` - Exponential backoff
- `linear` - Linear increase

## Testing API

### TestSource

```python
from dataflow.testing import TestSource

test_data = [1, 2, 3, 4, 5]
source = TestSource(test_data)
```

### TestSink

```python
from dataflow.testing import TestSink

sink = TestSink()
data.write(sink)

# Get results
results = sink.get_results()
```

### Assertions

```python
from dataflow.testing import assert_equal, assert_count

# Assert equal
assert_equal(actual, expected)

# Assert count
assert_count(stream, expected_count)
```

## Metrics API

### Built-in Metrics

Access metrics programmatically:

```python
from dataflow import Metrics

metrics = pipeline.metrics()

# Get metric values
events_processed = metrics.get("events_processed_total")
latency = metrics.get("latency_p99")
```

### Custom Metrics

Add custom metrics:

```python
from dataflow.metrics import Counter, Gauge, Histogram

# Counter
errors = Counter("custom_errors", "Number of custom errors")
errors.inc()

# Gauge
queue_size = Gauge("queue_size", "Current queue size")
queue_size.set(100)

# Histogram
latency = Histogram("api_latency", "API call latency")
latency.observe(0.5)
```

## Configuration API

### Programmatic Configuration

```python
from dataflow import Config

config = Config()
config.set("runtime.workers", 8)
config.set("runtime.memory", "16GB")

pipeline = Pipeline("my-pipeline", config=config)
```

### Load from File

```python
config = Config.from_file("dataflow.yaml")
```

### Environment Variables

```python
config = Config.from_env(prefix="DATAFLOW_")
```

## CLI API

Run DataFlow from Python code:

```python
from dataflow.cli import run_pipeline

run_pipeline(
    pipeline_file="my_pipeline.py",
    config="config.yaml",
    profile="prod"
)
```

## Type Hints

DataFlow supports type hints for better IDE support:

```python
from dataflow import Pipeline, DataStream, KafkaSource
from typing import Dict, Any

def process_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {"processed": event["value"] * 2}

pipeline: Pipeline = Pipeline("typed")
stream: DataStream = pipeline.read(KafkaSource("topic"))
result: DataStream = stream.map(process_event)
```

## Examples

See complete examples:
- [Basic pipeline](../getting-started/quick-start.md)
- [Advanced patterns](../guides/patterns-guide.md)
- [Example repository](https://github.com/dataflow/examples)

## API Versions

This documentation covers DataFlow API v2.4.

**Version compatibility:**
- v2.x - Stable, backward compatible
- v1.x - Deprecated, upgrade to v2.x

See [Migration Guide](migration-v2.md) for upgrading from v1.x.

## Next Steps

- Read [User Guide](../guides/user-guide.md) for usage patterns
- Explore [CLI Reference](cli.md) for command-line tools
- Check [Configuration Reference](config.md) for all config options
