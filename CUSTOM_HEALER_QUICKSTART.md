# Custom Healer Quick Start

**Get started creating custom healers in 5 minutes.**

---

## 1. Copy Template

```bash
cp templates/custom_healer_template.py guardian/healers/my_healer.py
```

---

## 2. Customize Class

```python
# Change class name
class MyCustomHealer(HealingSystem):
    """Brief description of what this healer does."""

    def __init__(self, config):
        super().__init__(config)

        # Load your config
        my_config = config.get('healers', {}).get('my_healer', {})
        self.option = my_config.get('option', 'default')

        # Setup logger
        from guardian.core.logger import setup_logger
        self.logger = setup_logger('my_healer')
```

---

## 3. Implement Detection

```python
def _has_issue(self, line: str) -> bool:
    """Check if line has the issue."""
    # Example: Detect lines with TODO
    return 'TODO:' in line

def _analyze_file(self, file_path: Path) -> List[Change]:
    """Find all issues in file."""
    changes = []
    content = file_path.read_text()

    for line_num, line in enumerate(content.split('\n'), start=1):
        if self._has_issue(line):
            change = self._create_fix_for_line(
                file_path, line_num, line, content
            )
            if change:
                changes.append(change)

    return changes
```

---

## 4. Generate Fixes

```python
def _create_fix_for_line(self, file_path, line_num, line, full_content):
    """Create a fix for this issue."""

    # Generate fix
    old_content = line
    new_content = self._fix_line(line)  # Your fix logic

    # Calculate confidence
    confidence = self._calculate_confidence(old_content, new_content, file_path)

    return Change(
        file=file_path,
        line=line_num,
        old_content=old_content,
        new_content=new_content,
        confidence=confidence,
        reason="Clear explanation of fix",
        healer="my_healer"
    )
```

---

## 5. Add Configuration

Edit `config.toml`:

```toml
[healers.my_healer]
enabled = true
option = "value"
```

---

## 6. Test It

```bash
# Check mode (dry run)
python -m guardian.cli check --healer my_healer

# Heal mode (apply fixes)
python -m guardian.cli heal --healer my_healer --min-confidence 0.90
```

---

## Complete Example

See `examples/custom_healer_example/` for a working example:

```bash
# Run demo
cd examples/custom_healer_example/
./demo.sh

# Run tests
pytest test_fix_typos.py -v
```

---

## Key Methods to Implement

### Required

```python
def check(self) -> HealingReport:
    """Scan files and return proposed fixes."""
    # 1. Find files
    # 2. Analyze each file
    # 3. Return report

def heal(self, min_confidence=None) -> HealingReport:
    """Apply fixes above confidence threshold."""
    # 1. Run check()
    # 2. Filter by confidence
    # 3. Apply validated changes
    # 4. Return report
```

### Optional (Override to Customize)

```python
def validate_change(self, change: Change) -> bool:
    """Validate before applying (add custom checks)."""
    if not super().validate_change(change):
        return False
    # Add your validation here
    return True

def _calculate_confidence(self, old, new, file) -> float:
    """Calculate confidence score."""
    factors = ConfidenceFactors(
        pattern_match=1.0,      # How well pattern matched
        change_magnitude=0.9,   # Size of change (smaller = higher)
        risk_assessment=0.8,    # Risk level (lower = higher)
        historical_accuracy=0.9 # Past success rate
    )
    return calculate_confidence(factors)
```

---

## Confidence Thresholds

| Confidence | Action | Use For |
|------------|--------|---------|
| **≥ 0.95** | Auto-commit | Exact matches, typo fixes |
| **0.90-0.94** | Auto-stage | Strong patterns, low risk |
| **0.80-0.89** | Review | Fuzzy matches, medium risk |
| **< 0.80** | Report only | Complex changes, high risk |

---

## Testing Pattern

```python
import pytest
from pathlib import Path
from my_healer import MyCustomHealer

@pytest.fixture
def healer(tmp_path):
    config = {
        'project': {
            'root': str(tmp_path),
            'doc_root': str(tmp_path / 'docs')
        },
        'healers': {'my_healer': {'enabled': True}}
    }
    (tmp_path / 'docs').mkdir()
    return MyCustomHealer(config)

def test_check_finds_issues(healer, tmp_path):
    # Create test file
    test_file = tmp_path / 'docs' / 'test.md'
    test_file.write_text("# Test\nTODO: fix this")

    # Run check
    report = healer.check()

    # Verify
    assert report.issues_found == 1

def test_heal_applies_fixes(healer, tmp_path):
    # Create test file
    test_file = tmp_path / 'docs' / 'test.md'
    test_file.write_text("# Test\nTODO: fix this")

    # Run heal
    report = healer.heal()

    # Verify
    assert report.issues_fixed == 1
    assert "TODO:" not in test_file.read_text()
```

---

## Common Patterns

### Pattern: Skip Code Blocks

```python
def _analyze_file(self, file_path):
    changes = []
    lines = file_path.read_text().split('\n')
    in_code_block = False

    for line_num, line in enumerate(lines, start=1):
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue  # Skip code

        # Process line...

    return changes
```

### Pattern: Regex Matching

```python
import re

def __init__(self, config):
    super().__init__(config)
    # Compile once for performance
    self.pattern = re.compile(r'your_pattern')

def _has_issue(self, line):
    return bool(self.pattern.search(line))
```

### Pattern: Multiple Fixes per Line

```python
def _create_fix_for_line(self, file_path, line_num, line, content):
    fixed_line = line

    # Apply multiple fixes
    for find, replace in self.replacements.items():
        if find in fixed_line:
            fixed_line = fixed_line.replace(find, replace)

    if fixed_line != line:
        return Change(...)

    return None
```

---

## Resources

- **Template**: `templates/custom_healer_template.py`
- **Full Guide**: `docs/CUSTOM_HEALERS.md`
- **Example**: `examples/custom_healer_example/`
- **Base Classes**: `guardian/core/base.py`
- **Confidence**: `guardian/core/confidence.py`

---

## Help

```bash
# View template
cat templates/custom_healer_template.py

# Read full guide
less docs/CUSTOM_HEALERS.md

# Try example
cd examples/custom_healer_example/
./demo.sh

# Get help
python -m guardian.cli --help
```

---

**Ready to build? Start with**: `cp templates/custom_healer_template.py guardian/healers/my_healer.py`
