# Contributing to Doc Guardian

Thank you for your interest in contributing to Doc Guardian! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

---

## Code of Conduct

This project follows [Anthropic's Code of Conduct](https://www.anthropic.com/code-of-conduct). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

---

## Getting Started

### Types of Contributions

We welcome several types of contributions:

1. **Bug Reports** - Found a bug? Open an issue with reproduction steps
2. **Feature Requests** - Have an idea? Open an issue to discuss
3. **Bug Fixes** - Fix a bug and submit a pull request
4. **New Healers** - Create a new healing system
5. **Documentation** - Improve docs, fix typos, add examples
6. **Tests** - Add test coverage

### Before You Start

1. Check existing [issues](https://github.com/anthropics/doc-guardian/issues) to avoid duplicates
2. For large changes, open an issue first to discuss the approach
3. Read through this contributing guide

---

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- A text editor or IDE

### Clone and Setup

```bash
# Fork the repository on GitHub first, then:
git clone https://github.com/YOUR_USERNAME/doc-guardian.git
cd doc-guardian

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Or install manually
pip install pytest pytest-cov black isort mypy
```

### Verify Setup

```bash
# Run tests
pytest tests/

# Run the tool
python guardian/heal.py --config config.toml.template --list
```

---

## Making Changes

### Branch Naming

Use descriptive branch names:

```
feature/add-yaml-support
fix/broken-link-detection
docs/improve-readme
test/add-staleness-tests
```

### Commit Messages

Follow conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `test` - Adding or updating tests
- `refactor` - Code change that neither fixes a bug nor adds a feature
- `style` - Formatting, missing semicolons, etc.
- `chore` - Maintenance tasks

Examples:
```
feat(healers): add YAML support to sync_canonical

fix(broken-links): handle relative paths with ..

docs(readme): add installation instructions for Windows

test(staleness): add tests for timestamp parsing
```

### Keep Changes Focused

- One logical change per commit
- One feature/fix per pull request
- If you find an unrelated issue, create a separate PR

---

## Pull Request Process

### Before Submitting

1. **Run tests**: `pytest tests/`
2. **Format code**: `black guardian/ tests/`
3. **Sort imports**: `isort guardian/ tests/`
4. **Check types**: `mypy guardian/`
5. **Update docs** if needed

### Submitting

1. Push your branch to your fork
2. Open a pull request against `main`
3. Fill out the PR template completely
4. Link any related issues

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Test addition

## Testing
How did you test these changes?

## Checklist
- [ ] Tests pass locally
- [ ] Code follows project style
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. A maintainer will review your PR
2. Address any feedback
3. Once approved, a maintainer will merge

---

## Coding Standards

### Python Style

We follow PEP 8 with these tools:

- **Black** for formatting (line length 100)
- **isort** for import sorting
- **mypy** for type checking

```bash
# Format code
black guardian/ tests/ --line-length 100

# Sort imports
isort guardian/ tests/

# Type check
mypy guardian/
```

### Code Organization

```
guardian/
  core/           # Base classes and utilities
    base.py       # HealingSystem, HealingReport, Change
    confidence.py # Confidence scoring
    git_utils.py  # Git operations
    validation.py # Syntax validation
  healers/        # Individual healing systems
    fix_broken_links.py
    detect_staleness.py
    ...
  heal.py         # Main orchestrator CLI
  install.py      # Hook installation CLI
  rollback.py     # Rollback CLI
```

### Naming Conventions

- Classes: `PascalCase` (e.g., `HealingSystem`)
- Functions/methods: `snake_case` (e.g., `fix_broken_link`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CONFIDENCE`)
- Private: prefix with `_` (e.g., `_internal_method`)

### Docstrings

Use Google-style docstrings:

```python
def calculate_confidence(factors: dict) -> float:
    """Calculate confidence score from multiple factors.

    Args:
        factors: Dictionary with keys 'pattern', 'magnitude', 'risk', 'history'
            and float values between 0.0 and 1.0.

    Returns:
        Weighted confidence score between 0.0 and 1.0.

    Raises:
        ValueError: If any factor is outside the 0.0-1.0 range.

    Example:
        >>> calculate_confidence({'pattern': 0.9, 'magnitude': 0.8, 'risk': 0.7, 'history': 0.9})
        0.84
    """
```

---

## Testing

### Test Structure

```
tests/
  test_healers/
    test_fix_broken_links.py
    test_detect_staleness.py
    ...
  test_core/
    test_confidence.py
    test_validation.py
    ...
  fixtures/
    sample_docs/
    configs/
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=guardian --cov-report=html

# Run specific test file
pytest tests/test_manage_collapsed.py

# Run specific test
pytest tests/test_manage_collapsed.py::test_collapse_long_section

# Run with verbose output
pytest tests/ -v
```

### Writing Tests

```python
import pytest
from guardian.healers.fix_broken_links import FixBrokenLinksHealer

class TestFixBrokenLinks:
    """Tests for the FixBrokenLinksHealer."""

    @pytest.fixture
    def healer(self, tmp_path):
        """Create a healer instance with test config."""
        config = {
            'project': {'root': str(tmp_path), 'doc_root': 'docs/'},
            'healers': {'fix_broken_links': {'enabled': True}}
        }
        return FixBrokenLinksHealer(config)

    def test_detects_broken_link(self, healer, tmp_path):
        """Should detect a link to a non-existent file."""
        # Arrange
        doc = tmp_path / "docs" / "test.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("[Link](missing.md)")

        # Act
        report = healer.check()

        # Assert
        assert report.issues_found == 1
        assert "missing.md" in str(report.changes[0])

    def test_fixes_broken_link(self, healer, tmp_path):
        """Should fix a broken link when file was moved."""
        # Arrange
        docs = tmp_path / "docs"
        docs.mkdir(parents=True)
        (docs / "test.md").write_text("[Link](old.md)")
        (docs / "new.md").write_text("# New File")

        # Act
        report = healer.heal(min_confidence=0.8)

        # Assert
        assert report.issues_fixed == 1
```

### Test Requirements

- All new features need tests
- Bug fixes should include a regression test
- Aim for 80%+ coverage on new code
- Tests should be fast (< 1 second each)

---

## Documentation

### When to Update Docs

- New features need documentation
- API changes need updates
- Bug fixes may need clarification
- Examples should be kept current

### Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview and quick start |
| `CONFIG_GUIDE.md` | Configuration reference |
| `CONTRIBUTING.md` | This file |
| `guardian/UTILITIES.md` | CLI utilities |
| `docs/healers/*.md` | Individual healer docs |

### Documentation Style

- Use clear, concise language
- Include code examples
- Show expected output
- Link to related docs

---

## Questions?

- Open a [GitHub Issue](https://github.com/anthropics/doc-guardian/issues)
- Check existing [Discussions](https://github.com/anthropics/doc-guardian/discussions)

Thank you for contributing!
