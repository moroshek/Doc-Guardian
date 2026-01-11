# Testing Guide

Comprehensive guide to testing DataFlow.

**Last Updated:** 2025-01-08

## Testing Philosophy

DataFlow uses a multi-layered testing approach:

1. **Unit Tests** - Test individual components (functions, classes)
2. **Integration Tests** - Test component interactions
3. **E2E Tests** - Test complete workflows
4. **Performance Tests** - Benchmark throughput and latency

## Running Tests

### All Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=dataflow --cov-report=html

# Parallel execution
pytest -n auto
```

### Specific Test Types

```bash
# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/ -m e2e

# Specific file
pytest tests/unit/test_pipeline.py

# Specific test
pytest tests/unit/test_pipeline.py::test_pipeline_map
```

### Test Markers

Use markers to categorize tests:

```bash
# Run slow tests
pytest -m slow

# Skip slow tests
pytest -m "not slow"

# Integration tests
pytest -m integration

# Unit tests only (default)
pytest -m "not integration and not e2e"
```

## Writing Unit Tests

Unit tests should be fast, isolated, and deterministic.

### Basic Structure

```python
# tests/unit/test_transforms.py
import pytest
from dataflow.transforms import MapTransform

class TestMapTransform:
    def test_basic_map(self):
        transform = MapTransform(lambda x: x * 2)
        result = transform.apply(5)
        assert result == 10

    def test_map_with_none(self):
        transform = MapTransform(lambda x: x * 2)
        with pytest.raises(TypeError):
            transform.apply(None)

    @pytest.mark.parametrize("input,expected", [
        (1, 2),
        (5, 10),
        (10, 20),
    ])
    def test_map_parameterized(self, input, expected):
        transform = MapTransform(lambda x: x * 2)
        assert transform.apply(input) == expected
```

### Using Fixtures

```python
# tests/conftest.py
import pytest
from dataflow import Pipeline

@pytest.fixture
def test_pipeline():
    """Create a test pipeline."""
    return Pipeline("test-pipeline")

@pytest.fixture
def sample_data():
    """Sample test data."""
    return [1, 2, 3, 4, 5]

# In test file
def test_with_fixtures(test_pipeline, sample_data):
    from dataflow.testing import TestSource

    result = test_pipeline.read(TestSource(sample_data)) \
        .map(lambda x: x * 2) \
        .collect()

    assert result == [2, 4, 6, 8, 10]
```

### Mocking

Use mocks for external dependencies:

```python
from unittest.mock import Mock, patch, MagicMock

def test_kafka_source_with_mock():
    # Mock Kafka consumer
    mock_consumer = Mock()
    mock_consumer.poll.return_value = [
        Mock(value=b'{"id": 1}'),
        Mock(value=b'{"id": 2}'),
    ]

    with patch('kafka.KafkaConsumer', return_value=mock_consumer):
        source = KafkaSource("topic")
        data = list(source.read())

        assert len(data) == 2
        assert data[0]["id"] == 1
```

## Writing Integration Tests

Integration tests verify component interactions.

### Docker Containers

Use testcontainers for real services:

```python
# tests/integration/test_kafka.py
import pytest
from testcontainers.kafka import KafkaContainer
from dataflow import Pipeline, KafkaSource, KafkaSink

@pytest.fixture(scope="module")
def kafka():
    with KafkaContainer() as container:
        yield container.get_bootstrap_server()

@pytest.mark.integration
def test_kafka_pipeline(kafka):
    # Write test data
    pipeline_write = Pipeline("write")
    pipeline_write.read(TestSource([{"id": 1}, {"id": 2}])) \
        .write(KafkaSink("test-topic", bootstrap_servers=kafka))
    pipeline_write.run()

    # Read and verify
    pipeline_read = Pipeline("read")
    data = pipeline_read.read(KafkaSource("test-topic", bootstrap_servers=kafka)) \
        .collect()

    assert len(data) == 2
```

### Database Tests

```python
# tests/integration/test_postgres.py
import pytest
from testcontainers.postgres import PostgresContainer
from dataflow import DatabaseSource, DatabaseSink

@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:14") as container:
        conn_string = container.get_connection_url()
        # Setup schema
        setup_database(conn_string)
        yield conn_string

@pytest.mark.integration
def test_database_pipeline(postgres):
    pipeline = Pipeline("db-test")

    # Read from source table
    data = pipeline.read(DatabaseSource(
        query="SELECT * FROM events",
        connection_string=postgres
    ))

    # Transform and write to destination
    data.map(transform_event) \
        .write(DatabaseSink(
            table="processed_events",
            connection_string=postgres
        ))

    pipeline.run()

    # Verify results
    verify_database_content(postgres)
```

## Writing E2E Tests

E2E tests verify complete workflows.

### Full Pipeline Test

```python
# tests/e2e/test_pipeline_e2e.py
import pytest
from dataflow import Pipeline

@pytest.mark.e2e
def test_full_etl_pipeline(test_cluster):
    """
    Test complete ETL workflow:
    1. Read from Kafka
    2. Transform data
    3. Aggregate by window
    4. Write to database
    """
    pipeline = Pipeline("etl-e2e")

    # Configure pipeline
    events = pipeline.read(KafkaSource(
        topic="raw-events",
        bootstrap_servers=test_cluster.kafka
    ))

    # Transform
    transformed = events \
        .map(parse_event) \
        .filter(lambda e: e["valid"]) \
        .map(enrich_event)

    # Aggregate
    windowed = transformed \
        .window(Window.tumbling(minutes=5)) \
        .aggregate(Aggregate.count())

    # Write
    windowed.write(DatabaseSink(
        table="metrics",
        connection_string=test_cluster.postgres
    ))

    # Run pipeline
    pipeline.run()

    # Verify results
    verify_metrics_table(test_cluster.postgres)
```

### Performance Tests

```python
# tests/e2e/test_performance.py
import pytest
import time

@pytest.mark.e2e
@pytest.mark.slow
def test_throughput(test_cluster):
    """Test pipeline handles 10K events/sec."""
    pipeline = Pipeline("throughput-test")

    # Generate load
    events_count = 100000
    start_time = time.time()

    pipeline.read(TestSource(range(events_count))) \
        .map(transform) \
        .write(KafkaSink("output", bootstrap_servers=test_cluster.kafka))

    pipeline.run()

    duration = time.time() - start_time
    throughput = events_count / duration

    assert throughput >= 10000, f"Throughput {throughput:.0f} < 10000 events/sec"
```

## Test Helpers

### TestSource and TestSink

```python
from dataflow.testing import TestSource, TestSink

# Test source with in-memory data
source = TestSource([1, 2, 3, 4, 5])

# Test sink to collect output
sink = TestSink()
pipeline.read(source).write(sink)
pipeline.run()

# Verify results
assert sink.get_results() == [expected_data]
```

### Assertions

```python
from dataflow.testing import assert_equal, assert_count, assert_schema

# Assert equal (order-independent)
assert_equal(actual, expected)

# Assert count
assert_count(results, expected_count)

# Assert schema
assert_schema(results, {
    "id": int,
    "name": str,
    "value": float
})
```

### Time Mocking

```python
from unittest.mock import patch
from datetime import datetime

with patch('dataflow.utils.now') as mock_now:
    mock_now.return_value = datetime(2025, 1, 1)
    # Test time-dependent code
```

## Testing Best Practices

### 1. Test Organization

```
tests/
├── unit/              # Fast, isolated tests
│   ├── test_pipeline.py
│   ├── test_transforms.py
│   └── test_sources.py
├── integration/       # Component interaction tests
│   ├── test_kafka.py
│   └── test_postgres.py
├── e2e/              # Full workflow tests
│   └── test_pipeline_e2e.py
├── conftest.py       # Shared fixtures
└── requirements.txt  # Test dependencies
```

### 2. Test Naming

```python
# Good - descriptive names
def test_map_transform_doubles_values():
    pass

def test_filter_removes_invalid_events():
    pass

# Bad - vague names
def test_map():
    pass

def test_filter_works():
    pass
```

### 3. AAA Pattern

Use Arrange-Act-Assert pattern:

```python
def test_pipeline_map():
    # Arrange
    pipeline = Pipeline("test")
    source = TestSource([1, 2, 3])

    # Act
    result = pipeline.read(source) \
        .map(lambda x: x * 2) \
        .collect()

    # Assert
    assert result == [2, 4, 6]
```

### 4. Parametrized Tests

Test multiple inputs efficiently:

```python
@pytest.mark.parametrize("input,expected", [
    ([1, 2, 3], [2, 4, 6]),
    ([0, -1, 5], [0, -2, 10]),
    ([], []),
])
def test_map_various_inputs(input, expected):
    pipeline = Pipeline("test")
    result = pipeline.read(TestSource(input)) \
        .map(lambda x: x * 2) \
        .collect()
    assert result == expected
```

### 5. Test Isolation

Each test should be independent:

```python
# Good - each test is isolated
def test_a():
    pipeline = Pipeline("test-a")
    # Test logic

def test_b():
    pipeline = Pipeline("test-b")
    # Test logic

# Bad - tests share state
shared_pipeline = Pipeline("shared")

def test_a():
    # Uses shared_pipeline

def test_b():
    # Uses same shared_pipeline - could fail if test_a modifies it
```

## Coverage

### Running Coverage

```bash
# Generate coverage report
pytest --cov=dataflow --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html

# Coverage for specific module
pytest --cov=dataflow.transforms tests/unit/test_transforms.py
```

### Coverage Goals

- **Overall**: >80%
- **Critical paths**: >90%
- **New code**: 100%

### Excluding from Coverage

```python
def debug_helper():  # pragma: no cover
    # Debug-only code
    pass
```

## Continuous Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11"]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest --cov=dataflow --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Debugging Failed Tests

### Verbose Output

```bash
# Show print statements
pytest -s

# Verbose mode
pytest -v

# Show full error traces
pytest --tb=long
```

### Debugging Specific Test

```bash
# Run with debugger
pytest --pdb tests/unit/test_pipeline.py::test_specific

# Or add breakpoint in code
def test_specific():
    import pdb; pdb.set_trace()
    # Test code
```

### Logging

```python
import logging

def test_with_logging(caplog):
    caplog.set_level(logging.DEBUG)

    # Test code that logs

    assert "expected message" in caplog.text
```

## Performance Benchmarks

### Benchmark Tests

```python
# tests/benchmarks/test_throughput.py
import pytest

def test_map_performance(benchmark):
    """Benchmark map transformation."""
    pipeline = Pipeline("bench")
    data = list(range(100000))

    def run_pipeline():
        return pipeline.read(TestSource(data)) \
            .map(lambda x: x * 2) \
            .collect()

    result = benchmark(run_pipeline)
    assert len(result) == 100000
```

### Running Benchmarks

```bash
# Run benchmarks
pytest tests/benchmarks/ --benchmark-only

# Compare with baseline
pytest tests/benchmarks/ --benchmark-compare

# Save baseline
pytest tests/benchmarks/ --benchmark-save=baseline
```

## Test Data

### Fixtures for Common Data

```python
# tests/conftest.py
@pytest.fixture
def sample_events():
    return [
        {"id": 1, "type": "click", "timestamp": "2025-01-01T00:00:00"},
        {"id": 2, "type": "view", "timestamp": "2025-01-01T00:00:01"},
        {"id": 3, "type": "click", "timestamp": "2025-01-01T00:00:02"},
    ]

@pytest.fixture
def large_dataset():
    """Generate large dataset for performance tests."""
    return list(range(1000000))
```

### Data Factories

```python
from dataclasses import dataclass
import factory

@dataclass
class Event:
    id: int
    type: str
    timestamp: str

class EventFactory(factory.Factory):
    class Meta:
        model = Event

    id = factory.Sequence(lambda n: n)
    type = factory.Iterator(["click", "view", "purchase"])
    timestamp = factory.Faker("iso8601")

# In tests
def test_with_factory():
    events = EventFactory.build_batch(100)
    # Test with generated events
```

## Common Testing Patterns

### Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_async_pipeline():
    pipeline = AsyncPipeline("test")
    result = await pipeline.read(AsyncSource()) \
        .map(async_transform) \
        .collect()

    assert len(result) > 0
```

### Testing Error Handling

```python
def test_error_handling():
    pipeline = Pipeline("test")

    with pytest.raises(ValueError, match="Invalid input"):
        pipeline.read(TestSource([None])) \
            .map(lambda x: x.upper()) \
            .collect()
```

### Testing Configuration

```python
def test_config_loading(tmp_path):
    # Create temp config file
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
    runtime:
      workers: 4
    """)

    # Load and test
    config = Config.from_file(str(config_file))
    assert config.get("runtime.workers") == 4
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)
- [Python Testing Tools](https://wiki.python.org/moin/PythonTestingToolsTaxonomy)

## Next Steps

- Review [Development Guide](development.md) for setup
- Check [Code Style Guide](code-style.md) for standards
- See [CI/CD Guide](../operations/ci-cd-setup.md) for automation
