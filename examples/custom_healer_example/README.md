# Custom Healer Example: Fix Common Typos

**Complete working example of a custom healer for Doc Guardian.**

This example demonstrates:
- Dictionary-based typo detection and fixing
- High-confidence auto-commit workflow
- Case-preserving replacements
- Configuration with custom typo dictionary
- Full test suite

---

## Files

```
examples/custom_healer_example/
├── README.md              # This file
├── fix_typos_healer.py    # Complete healer implementation
├── config.toml            # Example configuration
├── test_fix_typos.py      # Test suite
└── sample_docs/           # Sample documentation with typos
    ├── guide.md
    └── reference.md
```

---

## Quick Start

### 1. Install the Healer

```bash
# Copy to healers directory
cp fix_typos_healer.py ../../guardian/healers/

# Add configuration
cat config.toml >> ../../config.toml
```

### 2. Test on Sample Docs

```bash
# Check mode (dry run)
cd ../..
python -m guardian.cli check --healer fix_typos

# Heal mode (apply fixes)
python -m guardian.cli heal --healer fix_typos --min-confidence 0.90
```

### 3. Run Tests

```bash
pytest test_fix_typos.py -v
```

---

## How It Works

### Detection

The healer scans markdown files for words matching a typo dictionary:

```python
typo_map = {
    'teh': 'the',
    'recieve': 'receive',
    'occured': 'occurred',
    'seperator': 'separator'
}
```

### Fixing

When a typo is found:
1. **Replace** with case-preserving logic (handles "Teh" → "The")
2. **Calculate confidence**: Dictionary matches = 0.95 (very high)
3. **Apply** if above threshold (default: 0.90)

### Confidence Scoring

```python
ConfidenceFactors(
    pattern_match=1.0,       # Exact dictionary match
    change_magnitude=0.95,   # Typically one word
    risk_assessment=1.0,     # Typo fix = very safe
    historical_accuracy=0.95 # 95% past success
)
# Result: ~0.98 (auto-commit)
```

---

## Configuration Options

```toml
[healers.fix_typos]
enabled = true
min_confidence = 0.90

# Case-sensitive matching
case_sensitive = false

# Preserve original case in replacement
preserve_case = true

# Skip code blocks
skip_code_blocks = true

# Custom typo dictionary
[healers.fix_typos.common_typos]
teh = "the"
recieve = "receive"
occured = "occurred"
seperator = "separator"
```

---

## Customization

### Add Your Own Typos

Edit `config.toml`:

```toml
[healers.fix_typos.common_typos]
your_typo = "correction"
another_typo = "another_correction"
```

### Adjust Confidence

Lower confidence for manual review:

```toml
[healers.fix_typos]
min_confidence = 0.70  # Report only
```

Higher confidence for auto-commit:

```toml
[healers.fix_typos]
min_confidence = 0.95  # Very strict
```

---

## Testing

### Run All Tests

```bash
pytest test_fix_typos.py -v
```

### Test Coverage

```bash
pytest test_fix_typos.py --cov=fix_typos_healer --cov-report=html
```

### Test Cases

- ✅ Detection of common typos
- ✅ Case-preserving replacement
- ✅ Skip code blocks
- ✅ Skip inline code
- ✅ Confidence scoring
- ✅ Multiple typos per line
- ✅ End-to-end workflow

---

## Extending

### Add Context-Aware Logic

```python
def _is_valid_replacement(self, line: str, typo: str, correction: str) -> bool:
    """Check if replacement makes sense in context."""

    # Example: Don't fix "teh" in "teh_variable_name"
    if f"_{typo}_" in line or f"_{typo}" in line or f"{typo}_" in line:
        return False

    # Example: Don't fix inside URLs
    if "http" in line and typo in line.split("http")[1]:
        return False

    return True
```

### Track Statistics

```python
def __init__(self, config):
    super().__init__(config)
    self.stats = {
        'typos_found': 0,
        'typos_fixed': 0,
        'most_common_typo': None
    }

def check(self):
    # ... existing code ...

    # Track most common
    typo_counts = Counter()
    for change in issues:
        typo_counts[change.reason] += 1

    if typo_counts:
        self.stats['most_common_typo'] = typo_counts.most_common(1)[0]

    return report
```

---

## Performance

Benchmarks on TCF documentation (559 files, ~2MB):

| Operation | Time | Files/sec |
|-----------|------|-----------|
| Check | 2.3s | 243 |
| Heal | 2.8s | 200 |

Optimization tips:
- Pre-compile regex patterns in `__init__`
- Use `rglob()` with specific patterns
- Skip large files (>1MB)
- Cache file reads when possible

---

## Next Steps

1. **Customize dictionary** - Add project-specific typos
2. **Integrate with CI** - Run on pre-commit hook
3. **Track metrics** - Monitor typo trends over time
4. **Add ML** - Learn new typos from git history

---

**Last Updated**: 2026-01-11
