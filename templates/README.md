# Doc Guardian Templates

**Production-ready templates for extending Doc Guardian.**

---

## Available Templates

### Custom Healer Template

**File**: `custom_healer_template.py`

**What it is**:
- Complete working healer implementation
- 500+ lines of fully documented code
- Ready to copy and customize
- Includes example usage and testing code

**What it includes**:
- ✅ Configuration loading with defaults
- ✅ Detection logic skeleton
- ✅ Confidence scoring implementation
- ✅ Error handling throughout
- ✅ Logging setup
- ✅ Validation methods
- ✅ Example usage at bottom
- ✅ Comprehensive inline documentation

**Quick Start**:
```bash
# 1. Copy template
cp custom_healer_template.py ../guardian/healers/my_healer.py

# 2. Edit class name and implement detection logic

# 3. Add to config.toml
[healers.my_healer]
enabled = true

# 4. Test it
python -m guardian.cli check --healer my_healer
```

**Learn More**:
- **Quick Start**: `../CUSTOM_HEALER_QUICKSTART.md` (5-minute guide)
- **Full Guide**: `../docs/CUSTOM_HEALERS.md` (comprehensive tutorial)
- **Example**: `../examples/custom_healer_example/` (working example with tests)

---

## Template Structure

### Class Hierarchy

```python
CustomHealerTemplate(HealingSystem)
    │
    ├── __init__(config)
    │   ├── Load healer config
    │   ├── Setup logging
    │   └── Initialize patterns/state
    │
    ├── check() → HealingReport
    │   ├── Find target files
    │   ├── Analyze each file
    │   ├── Propose changes
    │   └── Return report (mode="check")
    │
    ├── heal(min_confidence) → HealingReport
    │   ├── Run check()
    │   ├── Filter by confidence
    │   ├── Validate each change
    │   ├── Apply validated changes
    │   └── Return report (mode="heal")
    │
    └── Helper Methods
        ├── _find_target_files() → List[Path]
        ├── _analyze_file(file) → List[Change]
        ├── _has_issue(line) → bool
        ├── _create_fix_for_line(...) → Change
        ├── _calculate_confidence(...) → float
        └── validate_change(change) → bool
```

### Key Methods to Implement

#### Required (Abstract Methods)

```python
def check(self) -> HealingReport:
    """Scan files and identify issues."""
    # Implement your detection logic

def heal(self, min_confidence=None) -> HealingReport:
    """Apply fixes above confidence threshold."""
    # Template provides default implementation
```

#### Optional (Customize as Needed)

```python
def _find_target_files(self) -> List[Path]:
    """Override to customize which files to process."""

def _has_issue(self, line: str) -> bool:
    """Override to implement your detection logic."""

def _calculate_confidence(self, old, new, file) -> float:
    """Override to customize confidence scoring."""

def validate_change(self, change: Change) -> bool:
    """Override to add custom validation."""
```

---

## What to Customize

### 1. Class Name and Docstring

```python
# Before:
class CustomHealerTemplate(HealingSystem):
    """Custom healer for [describe what it does]."""

# After:
class FixTyposHealer(HealingSystem):
    """Auto-fix common typos in documentation."""
```

### 2. Configuration

```python
def __init__(self, config):
    super().__init__(config)

    # Load your healer's config
    my_config = config.get('healers', {}).get('my_healer', {})

    # Define your options
    self.option1 = my_config.get('option1', 'default')
    self.option2 = my_config.get('option2', 42)
```

### 3. Detection Logic

```python
def _has_issue(self, line: str) -> bool:
    """Implement your detection logic."""
    # Example: Detect TODOs
    return 'TODO:' in line and not line.strip().startswith('#')
```

### 4. Fix Generation

```python
def _create_fix_for_line(self, file_path, line_num, line, full_content):
    """Generate fix for detected issue."""
    old_content = line
    new_content = self._generate_fix(line)  # Your logic

    confidence = self._calculate_confidence(old_content, new_content, file_path)

    return Change(
        file=file_path,
        line=line_num,
        old_content=old_content,
        new_content=new_content,
        confidence=confidence,
        reason="Clear explanation",
        healer="my_healer"
    )
```

---

## Template Features

### Error Handling

```python
try:
    content = file_path.read_text()
except Exception as e:
    self.logger.error(f"Cannot read {file_path}: {e}")
    return []  # Return empty, don't crash
```

### Logging

```python
from guardian.core.logger import setup_logger

self.logger = setup_logger('my_healer')

self.logger.info("Starting check...")
self.logger.debug(f"Processing {file_path}")
self.logger.warning(f"Skipping invalid file")
self.logger.error(f"Failed: {error}")
```

### Confidence Scoring

```python
from guardian.core.confidence import (
    calculate_confidence,
    ConfidenceFactors,
    assess_change_magnitude,
    assess_risk_level
)

factors = ConfidenceFactors(
    pattern_match=1.0,       # How well pattern matched
    change_magnitude=0.9,    # Size of change (smaller = higher)
    risk_assessment=0.8,     # Risk level (lower = higher)
    historical_accuracy=0.9  # Past success rate
)

confidence = calculate_confidence(factors)
```

### Validation

```python
def validate_change(self, change: Change) -> bool:
    # Base validation (file exists, content matches)
    if not super().validate_change(change):
        return False

    # Add custom validation
    if not self._is_safe_change(change):
        self.logger.warning(f"Unsafe change: {change.reason}")
        return False

    return True
```

---

## Testing Your Healer

### Basic Test Structure

```python
import pytest
from pathlib import Path
from my_healer import MyHealer

@pytest.fixture
def healer(tmp_path):
    config = {
        'project': {
            'root': str(tmp_path),
            'doc_root': str(tmp_path / 'docs')
        },
        'healers': {
            'my_healer': {'enabled': True}
        }
    }
    (tmp_path / 'docs').mkdir()
    return MyHealer(config)

def test_check_finds_issues(healer, tmp_path):
    # Setup
    test_file = tmp_path / 'docs' / 'test.md'
    test_file.write_text("# Test\nIssue here")

    # Execute
    report = healer.check()

    # Verify
    assert report.issues_found == 1
    assert report.mode == "check"

def test_heal_applies_fixes(healer, tmp_path):
    # Setup
    test_file = tmp_path / 'docs' / 'test.md'
    test_file.write_text("# Test\nIssue here")

    # Execute
    report = healer.heal()

    # Verify
    assert report.issues_fixed == 1
    assert "Fixed content" in test_file.read_text()
```

---

## Configuration Examples

### Minimal

```toml
[healers.my_healer]
enabled = true
```

### With Options

```toml
[healers.my_healer]
enabled = true
min_confidence = 0.90
option1 = "value"
option2 = 42

[healers.my_healer.advanced]
feature1 = true
feature2 = false
```

### With Dictionary/List

```toml
[healers.my_healer]
enabled = true
patterns = ["pattern1", "pattern2", "pattern3"]

[healers.my_healer.replacements]
find1 = "replace1"
find2 = "replace2"
```

---

## Common Pitfalls

### ❌ Don't: Crash on Errors

```python
def _analyze_file(self, file_path):
    content = file_path.read_text()  # Crashes if file unreadable
```

### ✅ Do: Handle Errors Gracefully

```python
def _analyze_file(self, file_path):
    try:
        content = file_path.read_text()
    except Exception as e:
        self.logger.error(f"Cannot read {file_path}: {e}")
        return []
```

### ❌ Don't: Use Direct Config Access

```python
self.option = config['healers']['my_healer']['option']  # KeyError if missing
```

### ✅ Do: Use .get() with Defaults

```python
my_config = config.get('healers', {}).get('my_healer', {})
self.option = my_config.get('option', 'default_value')
```

### ❌ Don't: Assume Files Exist

```python
def validate_change(self, change):
    content = change.file.read_text()  # Crashes if deleted
```

### ✅ Do: Check File Exists

```python
def validate_change(self, change):
    if not change.file.exists():
        self.logger.error(f"File does not exist: {change.file}")
        return False
    # Continue validation...
```

---

## Performance Tips

### Compile Patterns Once

```python
# ❌ Don't compile in loop
def _has_issue(self, line):
    pattern = re.compile(r'pattern')  # Recompiles every time
    return pattern.search(line)

# ✅ Do compile in __init__
def __init__(self, config):
    super().__init__(config)
    self.pattern = re.compile(r'pattern')  # Compile once

def _has_issue(self, line):
    return self.pattern.search(line)
```

### Filter Files Early

```python
def _find_target_files(self):
    files = []
    for file in self.doc_root.rglob("*.md"):
        # Skip large files
        if file.stat().st_size > 1_000_000:
            continue
        # Skip excluded directories
        if any(ex in file.parts for ex in ['node_modules', '.git']):
            continue
        files.append(file)
    return files
```

---

## Resources

- **Template**: `custom_healer_template.py` (this directory)
- **Quick Start**: `../CUSTOM_HEALER_QUICKSTART.md`
- **Full Guide**: `../docs/CUSTOM_HEALERS.md`
- **Example**: `../examples/custom_healer_example/`
- **Base Classes**: `../guardian/core/base.py`
- **Built-in Healers**: `../guardian/healers/`

---

## Next Steps

1. **Copy template**: `cp custom_healer_template.py ../guardian/healers/my_healer.py`
2. **Read quick start**: `cat ../CUSTOM_HEALER_QUICKSTART.md`
3. **Try example**: `cd ../examples/custom_healer_example && ./demo.sh`
4. **Read full guide**: `less ../docs/CUSTOM_HEALERS.md`
5. **Implement your healer**: Edit `my_healer.py`
6. **Test it**: `pytest test_my_healer.py -v`
7. **Deploy**: Add to `config.toml` and run

---

**Questions?** See `../docs/CUSTOM_HEALERS.md` Troubleshooting section.

**Last Updated**: 2026-01-11
