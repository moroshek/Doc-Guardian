# Quick Start Guide

Get up and running with DataFlow in 5 minutes.

**Last Updated:** 2024-08-15

## Your First Pipeline

Let's build a simple pipeline that processes log files.

### Step 1: Create a Pipeline

Create a file called `my_pipeline.py`:

```python
from dataflow import Pipeline, TextSource, Filter, Print

# Create pipeline
pipeline = Pipeline("my-first-pipeline")

# Read log files
logs = pipeline.read(TextSource("./logs/*.log"))

# Filter for errors
errors = logs.filter(Filter.contains("ERROR"))

# Print results
errors.write(Print())

# Run
pipeline.run()
```

### Step 2: Run the Pipeline

```bash
python my_pipeline.py
```

You should see ERROR lines from your log files printed to the console.

## Example: Real-Time Analytics

Here's a more advanced example that processes streaming data:

```python
from dataflow import Pipeline, KafkaSource, Window, Aggregate

pipeline = Pipeline("analytics")

# Read from Kafka
events = pipeline.read(KafkaSource("events-topic"))

# Window by 5 minutes
windowed = events.window(Window.tumbling(minutes=5))

# Count events per window
counts = windowed.aggregate(Aggregate.count())

# Write to database
counts.write(DatabaseSink("postgresql://localhost/metrics"))

pipeline.run()
```

## Key Concepts

### Sources
Sources read data into your pipeline:
- `TextSource` - Read text files
- `KafkaSource` - Read from Kafka topics
- `DatabaseSource` - Query databases
- See [API Reference](../reference/api.md) for all sources

### Transformations
Transform data as it flows through:
- `map()` - Transform each element
- `filter()` - Keep only matching elements
- `window()` - Group by time windows
- `aggregate()` - Compute statistics

### Sinks
Sinks write data out:
- `Print()` - Print to console
- `FileSink()` - Write to files
- `KafkaSink()` - Write to Kafka
- `DatabaseSink()` - Write to database

## Configuration

Create a `dataflow.yaml` config file:

```yaml
runtime:
  workers: 4
  memory: 4GB
  checkpoint_interval: 60s

sources:
  kafka:
    bootstrap_servers: localhost:9092

sinks:
  database:
    connection_string: postgresql://localhost/mydb
```

See [Configuration Guide](/docs/reference/config.md) for all options.

## Next Steps

- Read the [User Guide](../guides/user-guide.md) for pipeline patterns
- Learn about [windowing and aggregation](../guides/user-manual.md#windowing)
- Explore [deployment options](../guides/admin-guide.md)
- Check out [example pipelines](https://github.com/dataflow/examples)

## Common Patterns

### Pattern 1: ETL
Extract, Transform, Load pattern:
```python
pipeline.read(Source) \
    .map(transform_fn) \
    .filter(validate_fn) \
    .write(Sink)
```

### Pattern 2: Stream Enrichment
Enrich streaming data with reference data:
```python
stream = pipeline.read(KafkaSource("events"))
reference = pipeline.read(DatabaseSource("users"))

enriched = stream.join(reference, on="user_id")
```

### Pattern 3: Aggregation
Compute rolling statistics:
```python
pipeline.read(Source) \
    .window(Window.sliding(minutes=10)) \
    .aggregate(Aggregate.sum("value"))
```

## Tips

- Start with small datasets while developing
- Use `.print()` to debug transformations
- Enable checkpointing for fault tolerance
- Monitor with the built-in dashboard at http://localhost:8080

## Troubleshooting

**Pipeline won't start?**
- Check your config file syntax
- Verify source connections
- See [Troubleshooting Guide](../guides/troubleshooting.md)

**Performance issues?**
- Increase worker count
- Tune batch sizes
- See [Performance Tuning](../guides/admin-guide.md#performance)

## Need Help?

Join our community:
- [Discord](https://discord.gg/dataflow)
- [GitHub Discussions](https://github.com/dataflow/dataflow/discussions)
- [Stack Overflow tag: dataflow](https://stackoverflow.com/questions/tagged/dataflow)
