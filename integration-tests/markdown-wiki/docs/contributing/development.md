# Development Guide

Guide for contributing to DataFlow development.

**Last Updated:** 2025-01-10

## Getting Started

### Prerequisites

- Python 3.9+
- Rust 1.70+ (for native extensions)
- Docker (for integration tests)
- Git

### Clone Repository

```bash
git clone https://github.com/dataflow/dataflow.git
cd dataflow
```

### Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Build native extensions
cargo build --release

# Verify setup
python -m pytest tests/
```

## Project Structure

```
dataflow/
├── src/
│   └── dataflow/
│       ├── api/          # Public API
│       ├── core/         # Core runtime
│       ├── sources/      # Data sources
│       ├── sinks/        # Data sinks
│       └── transforms/   # Transformations
├── rust/                 # Rust native extensions
├── tests/
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── e2e/             # End-to-end tests
├── docs/                # Documentation
├── examples/            # Example pipelines
├── benchmarks/          # Performance benchmarks
└── scripts/             # Build and dev scripts
```

## Development Workflow

### 1. Create Branch

```bash
git checkout -b feature/my-feature
```

**Branch naming:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code refactoring
- `test/` - Test improvements

### 2. Make Changes

Follow our coding standards:
- See [Code Style Guide](code-style.md)
- Write tests for new features
- Update documentation

### 3. Run Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# All tests
pytest

# With coverage
pytest --cov=dataflow --cov-report=html
```

### 4. Format Code

```bash
# Format Python
black src/ tests/
isort src/ tests/

# Lint Python
flake8 src/ tests/
mypy src/

# Format Rust
cd rust && cargo fmt
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

**Commit message format:**
```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Formatting
- `refactor` - Code refactoring
- `test` - Tests
- `chore` - Maintenance

### 6. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create Pull Request on GitHub.

## Code Organization

### Adding a New Source

1. Create source class in `src/dataflow/sources/`:

```python
# src/dataflow/sources/my_source.py
from dataflow.sources.base import Source
from typing import Iterator, Any

class MySource(Source):
    def __init__(self, config: dict):
        self.config = config

    def read(self) -> Iterator[Any]:
        # Implement reading logic
        pass

    def close(self):
        # Cleanup
        pass
```

2. Add tests in `tests/unit/sources/`:

```python
# tests/unit/sources/test_my_source.py
from dataflow.sources.my_source import MySource

def test_my_source():
    source = MySource({"key": "value"})
    data = list(source.read())
    assert len(data) > 0
```

3. Update documentation in `docs/reference/sources.md`

4. Add example in `examples/`

### Adding a New Sink

Similar to sources, create in `src/dataflow/sinks/`.

### Adding a Transformation

Create in `src/dataflow/transforms/`:

```python
# src/dataflow/transforms/my_transform.py
from dataflow.transforms.base import Transform
from typing import Any

class MyTransform(Transform):
    def apply(self, element: Any) -> Any:
        # Transform logic
        return transformed_element
```

## Testing

### Writing Tests

#### Unit Tests

Test individual components in isolation:

```python
# tests/unit/test_pipeline.py
from dataflow import Pipeline
from dataflow.testing import TestSource, TestSink

def test_pipeline_map():
    pipeline = Pipeline("test")
    result = pipeline.read(TestSource([1, 2, 3])) \
        .map(lambda x: x * 2) \
        .collect()

    assert result == [2, 4, 6]
```

#### Integration Tests

Test component interactions:

```python
# tests/integration/test_kafka_integration.py
import pytest
from dataflow import Pipeline, KafkaSource, KafkaSink

@pytest.mark.integration
def test_kafka_e2e(kafka_cluster):
    # Use fixture for Kafka cluster
    pipeline = Pipeline("test")
    pipeline.read(KafkaSource("input")) \
        .map(lambda x: x.upper()) \
        .write(KafkaSink("output"))

    pipeline.run()
    # Verify output
```

#### E2E Tests

Test full workflows:

```python
# tests/e2e/test_full_pipeline.py
@pytest.mark.e2e
def test_full_workflow(test_cluster):
    # Deploy pipeline
    # Run workload
    # Verify results
    pass
```

### Test Fixtures

Use pytest fixtures for common setup:

```python
# tests/conftest.py
import pytest
from testcontainers.kafka import KafkaContainer

@pytest.fixture(scope="session")
def kafka_cluster():
    with KafkaContainer() as kafka:
        yield kafka.get_bootstrap_server()
```

### Running Specific Tests

```bash
# Run specific file
pytest tests/unit/test_pipeline.py

# Run specific test
pytest tests/unit/test_pipeline.py::test_pipeline_map

# Run by marker
pytest -m integration

# Run with pattern
pytest -k "kafka"
```

## Debugging

### Using debugger

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use IDE debugger
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)
logger.debug("Debug message")
```

### Profiling

```bash
# CPU profiling
python -m cProfile -o profile.stats my_pipeline.py

# Analyze
python -m pstats profile.stats

# Memory profiling
python -m memory_profiler my_pipeline.py
```

## Building

### Build Python Package

```bash
# Build wheel
python -m build

# Install locally
pip install dist/dataflow-*.whl
```

### Build Rust Extensions

```bash
cd rust
cargo build --release
cargo test
```

### Build Documentation

```bash
cd docs
make html

# View docs
open _build/html/index.html
```

## Performance Testing

### Benchmarks

Run benchmarks:

```bash
pytest benchmarks/ --benchmark-only
```

Create new benchmark:

```python
# benchmarks/test_throughput.py
def test_map_throughput(benchmark):
    pipeline = Pipeline("bench")
    data = range(100000)

    def run():
        pipeline.read(TestSource(data)) \
            .map(lambda x: x * 2) \
            .collect()

    benchmark(run)
```

### Load Testing

```bash
# Generate load
python scripts/load_test.py --rps 10000 --duration 300
```

## Documentation

### Writing Documentation

Documentation lives in `docs/`:
- Use reStructuredText or Markdown
- Include code examples
- Add cross-references
- Update API reference for code changes

### Building Docs Locally

```bash
cd docs
pip install -r requirements.txt
make html
```

### API Documentation

Generated from docstrings:

```python
def my_function(arg1: str, arg2: int) -> bool:
    """
    One-line summary.

    Longer description with details.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When input is invalid

    Example:
        >>> my_function("test", 42)
        True
    """
    pass
```

## Release Process

### Version Bumping

Update version in:
- `src/dataflow/__init__.py`
- `Cargo.toml`
- `docs/conf.py`

### Creating Release

```bash
# Tag release
git tag -a v2.5.0 -m "Release v2.5.0"
git push origin v2.5.0

# Build artifacts
python -m build

# Upload to PyPI (maintainers only)
twine upload dist/*
```

### Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped
- [ ] Tag created
- [ ] Release notes written

## Troubleshooting Development Issues

### Tests Failing

```bash
# Clean build artifacts
rm -rf build/ dist/ *.egg-info
pip install -e ".[dev]" --force-reinstall

# Reset test database
docker-compose down -v
docker-compose up -d
```

### Import Errors

```bash
# Reinstall in editable mode
pip install -e .

# Check PYTHONPATH
echo $PYTHONPATH
```

### Rust Build Errors

```bash
# Update Rust
rustup update

# Clean build
cd rust && cargo clean && cargo build --release
```

## Getting Help

### Resources

- [Contributing Guide](../contributing/CONTRIBUTING.md)
- [Code Style Guide](code-style.md)
- [Testing Guide](testing.md)
- [Architecture Overview](../architecture/overview.md)

### Communication

- **Discord**: [discord.gg/dataflow](https://discord.gg/dataflow) - #dev channel
- **GitHub Discussions**: For design discussions
- **GitHub Issues**: For bug reports and feature requests

### Code Review

All contributions require code review:
- Be responsive to feedback
- Keep PRs focused and small
- Add tests for new features
- Update documentation

## Best Practices

1. **Write tests first** - TDD approach
2. **Keep commits atomic** - One logical change per commit
3. **Update docs** - Documentation is code
4. **Follow style guide** - Use formatters and linters
5. **Be responsive** - Address review feedback promptly
6. **Ask questions** - Use Discord for help

## Next Steps

- Read [Testing Guide](testing.md) for detailed testing practices
- Review [Code Style Guide](code-style.md) for coding standards
- Check [Architecture Docs](../architecture/design.md) for system design
- Browse [Examples](https://github.com/dataflow/examples) for patterns
