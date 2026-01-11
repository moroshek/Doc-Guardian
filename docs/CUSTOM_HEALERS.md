# Writing Custom Healers for Doc Guardian

**Complete guide to extending Doc Guardian with your own healers.**

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Healer Anatomy](#healer-anatomy)
3. [Step-by-Step Guide](#step-by-step-guide)
4. [Confidence Scoring](#confidence-scoring)
5. [Configuration](#configuration)
6. [Testing](#testing)
7. [Best Practices](#best-practices)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 5-Minute Custom Healer

```bash
# 1. Copy template
cp templates/custom_healer_template.py guardian/healers/fix_typos.py

# 2. Edit class name and implement logic
# (see Step-by-Step Guide below)

# 3. Add to config.toml
cat >> config.toml <<EOF
[healers.fix_typos]
enabled = true
common_typos = {"teh" = "the", "recieve" = "receive"}
EOF

# 4. Test it
python -m guardian.cli check --healer fix_typos
```

---

## Healer Anatomy

### What is a Healer?

A **healer** is a self-contained module that:
1. **Detects** specific documentation issues
2. **Proposes** fixes with confidence scores
3. **Applies** fixes above a confidence threshold
4. **Reports** results in a standard format

### Core Components

```python
class MyHealer(HealingSystem):
    def __init__(self, config):
        # Load configuration
        pass

    def check(self) -> HealingReport:
        # 1. Find files
        # 2. Detect issues
        # 3. Propose fixes
        # 4. Return report
        pass

    def heal(self, min_confidence=None) -> HealingReport:
        # 1. Run check()
        # 2. Filter by confidence
        # 3. Apply fixes
        # 4. Return report
        pass
```

### The Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  check()                                                    │
│  ├─ Find files                                              │
│  ├─ Analyze each file                                       │
│  │  ├─ Detect issues                                        │
│  │  ├─ Calculate confidence                                 │
│  │  └─ Create Change objects                                │
│  └─ Return HealingReport (mode="check")                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  heal(min_confidence)                                       │
│  ├─ Run check()                                             │
│  ├─ Filter changes by confidence                            │
│  ├─ For each high-confidence change:                        │
│  │  ├─ Validate                                             │
│  │  └─ Apply                                                │
│  └─ Return HealingReport (mode="heal")                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Guide

### Step 1: Copy Template

```bash
cp templates/custom_healer_template.py guardian/healers/my_healer.py
```

### Step 2: Rename Class

```python
# Before:
class CustomHealerTemplate(HealingSystem):
    """Custom healer for [describe what it does]."""

# After:
class FixTyposHealer(HealingSystem):
    """Auto-fix common typos in documentation."""
```

### Step 3: Configure Options

```python
def __init__(self, config: Dict[str, Any]):
    super().__init__(config)

    # Load healer-specific config
    typo_config = config.get('healers', {}).get('fix_typos', {})

    # Load typo dictionary
    self.typo_map = typo_config.get('common_typos', {
        'teh': 'the',
        'recieve': 'receive',
        'occured': 'occurred'
    })

    # Setup logger
    self.logger = setup_logger('fix_typos')
```

### Step 4: Implement Detection Logic

```python
def _has_issue(self, line: str) -> bool:
    """Check if line contains any typos."""
    words = re.findall(r'\b\w+\b', line.lower())
    return any(word in self.typo_map for word in words)

def _analyze_file(self, file_path: Path) -> List[Change]:
    """Analyze file and return proposed fixes."""
    changes = []
    content = file_path.read_text()
    lines = content.split('\n')

    for line_num, line in enumerate(lines, start=1):
        if self._has_issue(line):
            change = self._create_fix_for_line(
                file_path, line_num, line, content
            )
            if change:
                changes.append(change)

    return changes
```

### Step 5: Generate Fixes

```python
def _create_fix_for_line(
    self,
    file_path: Path,
    line_num: int,
    line_content: str,
    full_content: str
) -> Optional[Change]:
    """Create fix for typo on this line."""

    # Find and replace typos
    fixed_line = line_content
    typos_found = []

    for typo, correction in self.typo_map.items():
        if typo in line_content.lower():
            # Case-preserving replacement
            fixed_line = re.sub(
                rf'\b{typo}\b',
                correction,
                fixed_line,
                flags=re.IGNORECASE
            )
            typos_found.append(typo)

    # Calculate confidence
    confidence = self._calculate_confidence(
        line_content, fixed_line, file_path
    )

    return Change(
        file=file_path,
        line=line_num,
        old_content=line_content,
        new_content=fixed_line,
        confidence=confidence,
        reason=f"Fix typos: {', '.join(typos_found)}",
        healer="fix_typos"
    )
```

### Step 6: Calculate Confidence

```python
def _calculate_confidence(
    self,
    old_content: str,
    new_content: str,
    file_path: Path
) -> float:
    """Calculate confidence for typo fix."""

    factors = ConfidenceFactors(
        pattern_match=1.0,  # Exact dictionary match
        change_magnitude=assess_change_magnitude(old_content, new_content),
        risk_assessment=assess_risk_level('typo_fix'),  # Very safe
        historical_accuracy=0.95  # Typo fixes rarely wrong
    )

    return calculate_confidence(factors)
```

### Step 7: Add Configuration

Edit `config.toml`:

```toml
[healers.fix_typos]
enabled = true
min_confidence = 0.90

# Typo dictionary
[healers.fix_typos.common_typos]
teh = "the"
recieve = "receive"
occured = "occurred"
seperator = "separator"
```

### Step 8: Test It

```bash
# Check mode (dry run)
python -m guardian.cli check --healer fix_typos

# Heal mode (apply fixes)
python -m guardian.cli heal --healer fix_typos --min-confidence 0.95
```

---

## Confidence Scoring

### Multi-Factor Model

Confidence scores combine 4 factors:

```python
ConfidenceFactors(
    pattern_match=0.95,      # How well pattern matched (0.0-1.0)
    change_magnitude=0.90,   # Size of change (smaller = higher)
    risk_assessment=0.85,    # Risk level (lower = higher)
    historical_accuracy=0.92 # Past success rate (0.0-1.0)
)
```

### Factor Weights

Default weights (configurable):
- **Pattern**: 40% - Most important (did we recognize the issue?)
- **Magnitude**: 30% - How big is the change?
- **Risk**: 20% - How risky is this change?
- **History**: 10% - What's our track record?

### Scoring Guidelines

| Confidence | Action | Use Case |
|------------|--------|----------|
| **≥ 0.95** | Auto-commit | Exact matches, typo fixes from dictionary |
| **0.90-0.94** | Auto-stage | Strong pattern match, low risk |
| **0.80-0.89** | Stage for review | Fuzzy matches, medium risk |
| **< 0.80** | Report only | Complex changes, high risk |

### Example Calculations

```python
# High confidence: Exact typo fix
factors = ConfidenceFactors(
    pattern_match=1.0,       # Exact dictionary match
    change_magnitude=0.95,   # Single word change
    risk_assessment=1.0,     # Typo fix = very safe
    historical_accuracy=0.98 # 98% past success
)
# Result: 0.98 (auto-commit)

# Medium confidence: Fuzzy link match
factors = ConfidenceFactors(
    pattern_match=0.85,      # 85% similar path
    change_magnitude=0.90,   # Small change
    risk_assessment=0.80,    # Links = medium risk
    historical_accuracy=0.85 # 85% past success
)
# Result: 0.85 (auto-stage)

# Low confidence: Structural change
factors = ConfidenceFactors(
    pattern_match=0.70,      # Pattern partially matched
    change_magnitude=0.50,   # Large change
    risk_assessment=0.50,    # Structural = higher risk
    historical_accuracy=0.75 # 75% past success
)
# Result: 0.61 (report only)
```

### Customizing Weights

```python
# In your healer's __init__:
self.custom_weights = {
    'pattern': 0.50,    # Emphasize pattern matching
    'magnitude': 0.30,
    'risk': 0.15,
    'history': 0.05
}

# When calculating:
confidence = calculate_confidence(factors, weights=self.custom_weights)
```

---

## Configuration

### Healer Configuration Structure

```toml
[healers.my_healer]
enabled = true              # Enable/disable healer
min_confidence = 0.85       # Override default threshold

# Healer-specific options
option1 = "value"
option2 = 42
patterns = ["pattern1", "pattern2"]

# Nested config
[healers.my_healer.advanced]
feature1 = true
feature2 = false
```

### Loading Config

```python
def __init__(self, config: Dict[str, Any]):
    super().__init__(config)

    # Get healer section
    healer_config = config.get('healers', {}).get('my_healer', {})

    # Load with defaults
    self.option1 = healer_config.get('option1', 'default')
    self.option2 = healer_config.get('option2', 42)

    # Override min_confidence if specified
    if 'min_confidence' in healer_config:
        self.min_confidence = healer_config['min_confidence']

    # Load nested config
    advanced = healer_config.get('advanced', {})
    self.feature1 = advanced.get('feature1', True)
```

### Required vs Optional Config

```python
# Required config (raise if missing)
if 'required_option' not in healer_config:
    raise KeyError(
        "Missing required config: healers.my_healer.required_option"
    )
self.required_option = healer_config['required_option']

# Optional with default
self.optional = healer_config.get('optional', 'default_value')
```

---

## Testing

### Unit Tests

Create `tests/test_my_healer.py`:

```python
import pytest
from pathlib import Path
from guardian.healers.my_healer import MyHealer

@pytest.fixture
def config():
    return {
        'project': {
            'root': '/tmp/test_project',
            'doc_root': '/tmp/test_project/docs'
        },
        'healers': {
            'my_healer': {
                'enabled': True,
                'option1': 'test'
            }
        },
        'confidence': {
            'auto_commit_threshold': 0.90
        }
    }

@pytest.fixture
def healer(config, tmp_path):
    # Override paths to use temp directory
    config['project']['root'] = str(tmp_path)
    config['project']['doc_root'] = str(tmp_path / 'docs')
    (tmp_path / 'docs').mkdir()
    return MyHealer(config)

def test_check_finds_issues(healer, tmp_path):
    # Create test file with issue
    test_file = tmp_path / 'docs' / 'test.md'
    test_file.write_text("# Test\nThis has an teh issue.")

    # Run check
    report = healer.check()

    # Verify
    assert report.issues_found == 1
    assert report.mode == "check"
    assert len(report.changes) == 1

def test_heal_applies_fixes(healer, tmp_path):
    # Create test file
    test_file = tmp_path / 'docs' / 'test.md'
    test_file.write_text("# Test\nThis has an teh issue.")

    # Run heal
    report = healer.heal(min_confidence=0.90)

    # Verify
    assert report.issues_fixed == 1
    assert report.mode == "heal"
    assert "the" in test_file.read_text()

def test_confidence_scoring(healer):
    # Test confidence calculation
    old = "teh"
    new = "the"
    confidence = healer._calculate_confidence(old, new, Path("test.md"))

    assert 0.9 <= confidence <= 1.0
```

### Integration Tests

```python
def test_end_to_end_workflow(healer, tmp_path):
    """Test complete check → heal → verify workflow."""

    # Setup: Create files with issues
    (tmp_path / 'docs' / 'file1.md').write_text("teh issue")
    (tmp_path / 'docs' / 'file2.md').write_text("recieve email")

    # 1. Check finds all issues
    check_report = healer.check()
    assert check_report.issues_found == 2

    # 2. Heal applies fixes
    heal_report = healer.heal()
    assert heal_report.issues_fixed == 2

    # 3. Verify fixes applied
    assert "the issue" in (tmp_path / 'docs' / 'file1.md').read_text()
    assert "receive email" in (tmp_path / 'docs' / 'file2.md').read_text()

    # 4. Re-check finds no issues
    final_check = healer.check()
    assert final_check.issues_found == 0
```

### Running Tests

```bash
# Run all tests for your healer
pytest tests/test_my_healer.py -v

# Run with coverage
pytest tests/test_my_healer.py --cov=guardian.healers.my_healer

# Run integration tests only
pytest tests/test_my_healer.py -k integration
```

---

## Best Practices

### 1. Single Responsibility

Each healer should address **one specific problem**:

✅ **Good**: `FixBrokenLinksHealer` - Fixes broken internal links
✅ **Good**: `SyncCanonicalHealer` - Syncs content from canonical sources
❌ **Bad**: `FixEverythingHealer` - Tries to fix multiple unrelated issues

### 2. Fail Gracefully

```python
# Handle errors without crashing
try:
    content = file.read_text()
except Exception as e:
    self.logger.error(f"Cannot read {file}: {e}")
    errors.append(str(e))
    return []  # Return empty, don't crash
```

### 3. Log Everything Important

```python
self.logger.info(f"Scanning {len(files)} files...")
self.logger.debug(f"Analyzing {file_path}")
self.logger.warning(f"Skipping invalid file: {file_path}")
self.logger.error(f"Failed to apply fix: {error}")
```

### 4. Be Conservative

When in doubt, **lower the confidence score**:

```python
# If unsure, reduce confidence
if uncertain_condition:
    confidence *= 0.8  # Drop to auto-stage threshold
```

### 5. Validate Before Applying

```python
def validate_change(self, change: Change) -> bool:
    # Base validation
    if not super().validate_change(change):
        return False

    # Custom validation
    if not self._is_safe_change(change):
        self.logger.warning(f"Unsafe change detected: {change.reason}")
        return False

    return True
```

### 6. Document Edge Cases

```python
def _analyze_file(self, file_path: Path) -> List[Change]:
    """
    Analyze file for issues.

    Edge cases:
    - Empty files: Returns [] (no issues)
    - Binary files: Skipped (cannot read as text)
    - Symlinks: Followed (resolves to target)
    - Code blocks: Ignored (issues in code are intentional)
    """
    pass
```

### 7. Performance Considerations

```python
# Use generator for large file sets
def _find_target_files(self) -> List[Path]:
    # ❌ Don't load all files in memory
    # return list(self.doc_root.rglob("*"))

    # ✅ Filter as you go
    files = []
    for file in self.doc_root.rglob("*.md"):
        if self._should_process(file):
            files.append(file)
    return files
```

---

## Examples

### Example 1: Fix Common Typos

**Problem**: Documentation has recurring typos.

**Solution**: Dictionary-based typo fixer with high confidence.

```python
class FixTyposHealer(HealingSystem):
    """Fix common typos using dictionary."""

    def __init__(self, config):
        super().__init__(config)
        typo_config = config.get('healers', {}).get('fix_typos', {})
        self.typo_map = typo_config.get('common_typos', {})
        self.logger = setup_logger('fix_typos')

    def _analyze_file(self, file_path: Path) -> List[Change]:
        changes = []
        content = file_path.read_text()

        for typo, correction in self.typo_map.items():
            if typo in content:
                confidence = 0.95  # Dictionary = high confidence
                changes.append(Change(
                    file=file_path,
                    line=0,
                    old_content=typo,
                    new_content=correction,
                    confidence=confidence,
                    reason=f"Fix typo: {typo} → {correction}",
                    healer="fix_typos"
                ))

        return changes
```

### Example 2: Enforce Consistent Headers

**Problem**: Headers have inconsistent formatting (## vs ##).

**Solution**: Normalize header spacing.

```python
class NormalizeHeadersHealer(HealingSystem):
    """Enforce consistent header spacing."""

    def __init__(self, config):
        super().__init__(config)
        self.header_pattern = re.compile(r'^(#+)\s*(.+)$')
        self.logger = setup_logger('normalize_headers')

    def _analyze_file(self, file_path: Path) -> List[Change]:
        changes = []
        lines = file_path.read_text().split('\n')

        for line_num, line in enumerate(lines, start=1):
            match = self.header_pattern.match(line)
            if match:
                hashes, title = match.groups()
                # Normalize: exactly one space after hashes
                normalized = f"{hashes} {title.strip()}"

                if normalized != line:
                    changes.append(Change(
                        file=file_path,
                        line=line_num,
                        old_content=line,
                        new_content=normalized,
                        confidence=0.90,
                        reason="Normalize header spacing",
                        healer="normalize_headers"
                    ))

        return changes
```

### Example 3: Flag Outdated Dates

**Problem**: Documentation has "Last Updated" dates older than 6 months.

**Solution**: Flag stale dates for review (report only, don't auto-fix).

```python
from datetime import datetime, timedelta

class DetectStaleDatesHealer(HealingSystem):
    """Flag documentation with outdated 'Last Updated' dates."""

    def __init__(self, config):
        super().__init__(config)
        date_config = config.get('healers', {}).get('detect_stale_dates', {})
        self.stale_threshold_days = date_config.get('stale_days', 180)
        self.date_pattern = re.compile(r'Last Updated:\s*(\d{4}-\d{2}-\d{2})')
        self.logger = setup_logger('detect_stale_dates')

    def _analyze_file(self, file_path: Path) -> List[Change]:
        changes = []
        content = file_path.read_text()

        for match in self.date_pattern.finditer(content):
            date_str = match.group(1)
            last_updated = datetime.fromisoformat(date_str)
            age_days = (datetime.now() - last_updated).days

            if age_days > self.stale_threshold_days:
                # Low confidence = report only (human review required)
                changes.append(Change(
                    file=file_path,
                    line=0,
                    old_content=match.group(0),
                    new_content=f"Last Updated: {datetime.now().date()}",
                    confidence=0.50,  # Low = report only
                    reason=f"Stale date ({age_days} days old)",
                    healer="detect_stale_dates"
                ))

        return changes
```

---

## Troubleshooting

### Issue: Healer not found

**Error**: `Healer 'my_healer' not found`

**Solution**:
1. Check file is in `guardian/healers/my_healer.py`
2. Check class inherits from `HealingSystem`
3. Check `config.toml` has `[healers.my_healer]` section
4. Restart CLI to reload modules

### Issue: Config not loading

**Error**: `KeyError: 'healers.my_healer.option'`

**Solution**:
```python
# Use .get() with defaults instead of direct access
# ❌ Don't:
self.option = config['healers']['my_healer']['option']

# ✅ Do:
healer_config = config.get('healers', {}).get('my_healer', {})
self.option = healer_config.get('option', 'default_value')
```

### Issue: Changes not applied

**Debug checklist**:
1. Check confidence scores: `report.changes[0].confidence`
2. Check threshold: `min_confidence` vs actual confidence
3. Check validation: Override `validate_change()` with logging
4. Check file permissions: Is file writable?

```python
def validate_change(self, change: Change) -> bool:
    self.logger.debug(f"Validating: {change.file}:{change.line}")
    result = super().validate_change(change)
    self.logger.debug(f"Validation result: {result}")
    return result
```

### Issue: Low confidence scores

**Increase confidence by**:
1. **Better pattern matching**: Exact matches → 1.0, fuzzy → 0.8
2. **Smaller changes**: One-line changes → higher magnitude score
3. **Lower risk**: Typo fixes → 1.0, structural → 0.5
4. **Track history**: Keep success rate, use in calculations

### Issue: Performance problems

**Optimize**:
```python
# Cache compiled regexes
def __init__(self, config):
    self.pattern = re.compile(r'regex_pattern')  # Once

# Skip large files
def _should_process(self, file: Path) -> bool:
    return file.stat().st_size < 1_000_000  # Skip >1MB

# Use generators for large sets
def _find_files(self):
    for file in self.doc_root.rglob("*.md"):
        if self._should_process(file):
            yield file
```

---

## Advanced Topics

### Custom Validation

```python
def validate_change(self, change: Change) -> bool:
    # Base validation
    if not super().validate_change(change):
        return False

    # Check file is markdown
    if change.file.suffix != '.md':
        self.logger.error(f"Not a markdown file: {change.file}")
        return False

    # Validate generated content
    if not self._is_valid_markdown(change.new_content):
        self.logger.error(f"Invalid markdown generated")
        return False

    return True

def _is_valid_markdown(self, content: str) -> bool:
    """Check if content is syntactically valid markdown."""
    # Example: Check balanced brackets
    open_brackets = content.count('[')
    close_brackets = content.count(']')
    return open_brackets == close_brackets
```

### Incremental Processing

```python
class IncrementalHealer(HealingSystem):
    """Process only changed files since last run."""

    def __init__(self, config):
        super().__init__(config)
        self.state_file = Path('.guardian/state.json')

    def _find_target_files(self) -> List[Path]:
        """Find files changed since last run."""
        last_run = self._load_last_run_time()

        changed_files = []
        for file in self.doc_root.rglob("*.md"):
            if file.stat().st_mtime > last_run:
                changed_files.append(file)

        return changed_files

    def _load_last_run_time(self) -> float:
        if self.state_file.exists():
            import json
            state = json.loads(self.state_file.read_text())
            return state.get('last_run', 0)
        return 0

    def heal(self, min_confidence=None) -> HealingReport:
        report = super().heal(min_confidence)

        # Update state
        self._save_run_time()

        return report

    def _save_run_time(self):
        import json
        self.state_file.parent.mkdir(exist_ok=True)
        self.state_file.write_text(json.dumps({
            'last_run': time.time()
        }))
```

---

## Resources

- **Template**: `templates/custom_healer_template.py`
- **Examples**: `examples/custom_healer_example/`
- **Base Classes**: `guardian/core/base.py`
- **Confidence Model**: `guardian/core/confidence.py`
- **Existing Healers**: `guardian/healers/`

---

**Last Updated**: 2026-01-11
