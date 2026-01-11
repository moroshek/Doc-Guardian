# Code Style Guide

Coding standards and style guidelines for DataFlow.

**Last Updated:** 2025-01-10

## Overview

DataFlow follows industry-standard Python and Rust coding conventions with some project-specific additions.

## Python Code Style

### PEP 8 Compliance

Follow [PEP 8](https://peps.python.org/pep-0008/) with these configurations:

```ini
# .flake8
[flake8]
max-line-length = 100
extend-ignore = E203, W503
exclude = .git, __pycache__, build, dist
```

### Formatting with Black

Use Black for consistent formatting:

```bash
# Format code
black src/ tests/

# Check formatting
black --check src/ tests/
```

**Black configuration** (pyproject.toml):
```toml
[tool.black]
line-length = 100
target-version = ['py39']
include = '\.pyi?$'
```

### Import Sorting

Use isort for import organization:

```bash
# Sort imports
isort src/ tests/

# Check imports
isort --check src/ tests/
```

**isort configuration** (pyproject.toml):
```toml
[tool.isort]
profile = "black"
line_length = 100
multi_line_output = 3
```

### Type Hints

Use type hints for all public APIs:

```python
from typing import List, Dict, Optional, Union, Any

def process_events(
    events: List[Dict[str, Any]],
    filter_fn: Optional[callable] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Process events with optional filtering.

    Args:
        events: List of event dictionaries
        filter_fn: Optional filter function
        limit: Maximum number of events to return

    Returns:
        Processed events list
    """
    processed = []
    for event in events:
        if filter_fn is None or filter_fn(event):
            processed.append(event)
            if len(processed) >= limit:
                break
    return processed
```

### Type Checking

Use mypy for static type checking:

```bash
# Check types
mypy src/

# Check with strict mode
mypy --strict src/
```

**mypy configuration** (mypy.ini):
```ini
[mypy]
python_version = 3.9
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True

[mypy-tests.*]
disallow_untyped_defs = False
```

## Naming Conventions

### Variables and Functions

```python
# Snake case for variables and functions
user_count = 10
event_data = {}

def process_event(event):
    pass

def calculate_total_value(items):
    pass
```

### Classes

```python
# PascalCase for classes
class DataPipeline:
    pass

class KafkaSource:
    pass

class EventProcessor:
    pass
```

### Constants

```python
# UPPER_SNAKE_CASE for constants
MAX_WORKERS = 16
DEFAULT_TIMEOUT = 30
KAFKA_TOPIC_PREFIX = "dataflow-"
```

### Private Members

```python
class Example:
    def __init__(self):
        self._internal_state = {}  # Protected
        self.__private_data = []   # Private (name mangling)

    def public_method(self):
        pass

    def _internal_method(self):
        pass

    def __private_method(self):
        pass
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def complex_function(
    arg1: str,
    arg2: int,
    arg3: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    One-line summary of the function.

    More detailed description of what the function does,
    including any important details about behavior.

    Args:
        arg1: Description of arg1, what it's used for
        arg2: Description of arg2
        arg3: Optional list of strings, defaults to None

    Returns:
        Dictionary containing result data with keys:
        - 'status': Status string
        - 'data': Processed data
        - 'count': Number of items processed

    Raises:
        ValueError: If arg1 is empty
        TypeError: If arg2 is negative

    Example:
        >>> result = complex_function("test", 42)
        >>> print(result['status'])
        'success'

    Note:
        This function is thread-safe.

    Warning:
        Large values of arg2 may cause performance issues.
    """
    if not arg1:
        raise ValueError("arg1 cannot be empty")
    if arg2 < 0:
        raise TypeError("arg2 must be non-negative")

    # Implementation
    return {"status": "success", "data": [], "count": 0}
```

### Module Docstrings

```python
"""
Module for data source implementations.

This module contains various source implementations for reading
data from different systems like Kafka, databases, and files.

Classes:
    KafkaSource: Read from Kafka topics
    DatabaseSource: Read from SQL databases
    FileSource: Read from files

Functions:
    create_source: Factory function for creating sources

Example:
    >>> from dataflow.sources import KafkaSource
    >>> source = KafkaSource("my-topic")
    >>> data = source.read()
"""
```

### Class Docstrings

```python
class DataPipeline:
    """
    Main pipeline class for data processing.

    A DataPipeline orchestrates data flow from sources through
    transformations to sinks. Pipelines can be configured with
    various runtime options and executed synchronously or asynchronously.

    Attributes:
        name: Pipeline name for identification
        config: Configuration dictionary
        sources: List of configured sources
        sinks: List of configured sinks

    Example:
        >>> pipeline = DataPipeline("my-pipeline")
        >>> pipeline.read(KafkaSource("topic"))
        >>> pipeline.map(transform_fn)
        >>> pipeline.write(DatabaseSink("table"))
        >>> pipeline.run()
    """
    pass
```

## Code Organization

### File Structure

```python
# Standard imports first
import os
import sys
from typing import List, Dict

# Third-party imports
import numpy as np
import pandas as pd
from kafka import KafkaConsumer

# Local imports
from dataflow.core import Pipeline
from dataflow.sources.base import Source

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Module-level variables
_cache: Dict[str, Any] = {}

# Classes
class MyClass:
    pass

# Functions
def helper_function():
    pass

# Main execution
if __name__ == "__main__":
    main()
```

### Class Organization

```python
class Example:
    """Class docstring."""

    # Class variables
    class_var = "value"

    def __init__(self, arg):
        """Initialize instance."""
        # Instance variables
        self.arg = arg
        self._internal = None

    # Public methods
    def public_method(self):
        """Public method."""
        pass

    # Properties
    @property
    def value(self):
        """Get value."""
        return self._internal

    @value.setter
    def value(self, val):
        """Set value."""
        self._internal = val

    # Private/internal methods
    def _helper_method(self):
        """Internal helper."""
        pass

    # Special methods
    def __repr__(self):
        return f"Example(arg={self.arg})"

    def __eq__(self, other):
        return self.arg == other.arg
```

## Error Handling

### Exception Naming

```python
# Inherit from appropriate base class
class DataFlowError(Exception):
    """Base exception for DataFlow."""
    pass

class SourceError(DataFlowError):
    """Error in data source."""
    pass

class TransformError(DataFlowError):
    """Error in transformation."""
    pass
```

### Exception Handling

```python
# Be specific with exceptions
try:
    data = read_file(path)
except FileNotFoundError:
    logger.error(f"File not found: {path}")
    raise
except PermissionError:
    logger.error(f"Permission denied: {path}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise DataFlowError(f"Failed to read file: {path}") from e

# Use context managers
with open(path) as f:
    data = f.read()

# Custom context managers
@contextmanager
def database_connection(conn_string):
    conn = connect(conn_string)
    try:
        yield conn
    finally:
        conn.close()
```

## Best Practices

### 1. Keep Functions Small

```python
# Good - focused function
def validate_email(email: str) -> bool:
    """Validate email format."""
    return "@" in email and "." in email.split("@")[1]

# Bad - doing too much
def process_user_data(data):
    # Validate
    if "@" not in data["email"]:
        raise ValueError("Invalid email")
    # Transform
    data["name"] = data["name"].upper()
    # Store
    database.save(data)
    # Send email
    send_welcome_email(data["email"])
    # Log
    logger.info(f"Processed user {data['id']}")
```

### 2. Use List Comprehensions

```python
# Good - concise and readable
squares = [x**2 for x in range(10)]
evens = [x for x in numbers if x % 2 == 0]

# Avoid when complex
# Bad - too complex for comprehension
result = [
    transform(x) if condition(x) else default(x)
    for x in items
    if pre_filter(x) and not excluded(x)
]

# Better - use explicit loop for complex logic
result = []
for x in items:
    if not pre_filter(x) or excluded(x):
        continue
    result.append(transform(x) if condition(x) else default(x))
```

### 3. Use Generators for Large Data

```python
# Good - memory efficient
def read_large_file(path):
    """Generator for reading large files."""
    with open(path) as f:
        for line in f:
            yield line.strip()

# Usage
for line in read_large_file("large.txt"):
    process(line)
```

### 4. Avoid Mutable Default Arguments

```python
# Bad - mutable default
def add_item(item, items=[]):
    items.append(item)
    return items

# Good - use None
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### 5. Use with for Resources

```python
# Good - automatic cleanup
with open("file.txt") as f:
    data = f.read()

# Good - multiple resources
with open("input.txt") as fin, open("output.txt", "w") as fout:
    for line in fin:
        fout.write(line.upper())
```

## Rust Code Style

### Formatting

Use rustfmt:

```bash
cd rust
cargo fmt --check  # Check formatting
cargo fmt          # Format code
```

### Linting

Use clippy:

```bash
cargo clippy -- -D warnings
```

### Naming Conventions

```rust
// Snake case for variables and functions
let user_count = 10;
let event_data = HashMap::new();

fn process_event(event: Event) -> Result<()> {
    // ...
}

// PascalCase for types
struct DataPipeline {
    // ...
}

enum EventType {
    Click,
    View,
}

// SCREAMING_SNAKE_CASE for constants
const MAX_WORKERS: usize = 16;
const DEFAULT_TIMEOUT: Duration = Duration::from_secs(30);
```

### Documentation

```rust
/// Processes events from a source.
///
/// This function reads events from the given source and applies
/// the transformation function to each event.
///
/// # Arguments
///
/// * `source` - Event source to read from
/// * `transform` - Function to apply to each event
///
/// # Returns
///
/// Vector of transformed events
///
/// # Errors
///
/// Returns error if source fails to read
///
/// # Examples
///
/// ```
/// let events = process_events(source, |e| e.value * 2)?;
/// ```
pub fn process_events<F>(
    source: &dyn EventSource,
    transform: F,
) -> Result<Vec<Event>>
where
    F: Fn(&Event) -> i64,
{
    // Implementation
}
```

## Git Commit Messages

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting (no code change)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

### Examples

```bash
# Good commits
feat(kafka): add SASL authentication support
fix(pipeline): handle empty input gracefully
docs(api): update API reference for v2.4
refactor(transforms): simplify map implementation
test(integration): add Kafka integration tests

# With body
feat(windowing): add session window support

Implement session windows that group events based on
inactivity gaps. Windows close after specified gap
duration with no new events.

Closes #123
```

## Pre-commit Hooks

Install pre-commit hooks:

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

# Install
pre-commit install
```

## IDE Configuration

### VS Code

```json
// .vscode/settings.json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "editor.rulers": [100]
}
```

### PyCharm

1. Enable Black: Settings → Tools → Black
2. Enable isort: Settings → Tools → isort
3. Set line length to 100: Settings → Code Style → Python

## Code Review Checklist

- [ ] Follows PEP 8 / style guide
- [ ] Has type hints
- [ ] Has docstrings
- [ ] Has tests
- [ ] Tests pass
- [ ] Formatted with black/rustfmt
- [ ] Sorted imports with isort
- [ ] Passes mypy/clippy
- [ ] No security issues
- [ ] Performance considered
- [ ] Documentation updated

## Resources

- [PEP 8](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Rust Style Guidelines](https://doc.rust-lang.org/1.0.0/style/)
- [Black Documentation](https://black.readthedocs.io/)

## See Also

- [Development Guide](development.md) - Setup and workflow
- [Testing Guide](testing.md) - Testing practices
- [Contributing](CONTRIBUTING.md) - How to contribute
