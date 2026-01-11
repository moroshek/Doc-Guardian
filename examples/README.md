# Doc Guardian Examples

**Practical examples and templates for extending Doc Guardian.**

---

## Available Examples

### 1. Custom Healer Example: Fix Common Typos

**Location**: `custom_healer_example/`

**What it demonstrates**:
- Complete working healer implementation
- Dictionary-based detection
- High-confidence auto-commit workflow
- Case-preserving replacements
- Comprehensive test suite

**Files**:
- `fix_typos_healer.py` - Full healer implementation (400+ lines)
- `test_fix_typos.py` - Complete test suite (30+ tests)
- `config.toml` - Example configuration
- `sample_docs/` - Sample documentation with typos
- `demo.sh` - Interactive demo script
- `README.md` - Detailed documentation

**Quick Start**:
```bash
cd custom_healer_example/

# Run demo
./demo.sh

# Run tests
pytest test_fix_typos.py -v

# Install healer
cp fix_typos_healer.py ../../guardian/healers/
cat config.toml >> ../../config.toml
```

**Learn how to**:
- Create a custom healer from scratch
- Implement detection and fixing logic
- Calculate confidence scores
- Write comprehensive tests
- Configure and deploy your healer

---

## Using the Template

### Quick Start

```bash
# 1. Copy template
cp ../templates/custom_healer_template.py ../guardian/healers/my_healer.py

# 2. Edit (see CUSTOM_HEALERS.md guide)
# 3. Add configuration
# 4. Test
# 5. Deploy
```

### Complete Guide

See `docs/CUSTOM_HEALERS.md` for step-by-step instructions on:
- Healer anatomy
- Detection logic
- Confidence scoring
- Configuration
- Testing strategies
- Best practices

---

## Example Use Cases

### Typo Fixing
**Example**: `custom_healer_example/fix_typos_healer.py`
- Dictionary-based detection
- High confidence (0.95+)
- Auto-commit safe

### Link Fixing
**See**: `guardian/healers/fix_broken_links.py` (built-in)
- Fuzzy matching
- Path resolution
- Medium-high confidence (0.80-0.95)

### Content Synchronization
**See**: `guardian/healers/sync_canonical.py` (built-in)
- Template-driven
- Single source of truth
- High confidence (0.90+)

### Staleness Detection
**See**: `guardian/healers/detect_staleness.py` (built-in)
- Date comparison
- Low confidence (report only)
- Human review required

### Progressive Disclosure
**See**: `guardian/healers/enforce_disclosure.py` (built-in)
- Structure analysis
- Medium confidence (0.80-0.90)
- Automated collapse

---

## Contributing Examples

Have a custom healer you'd like to share?

### Steps

1. **Create directory**: `examples/your_example/`
2. **Add files**:
   - `your_healer.py` - Implementation
   - `test_your_healer.py` - Tests
   - `config.toml` - Configuration
   - `README.md` - Documentation
3. **Document**:
   - What problem it solves
   - How to use it
   - Configuration options
   - Test instructions
4. **Submit**: Open a pull request

### Template Structure

```
examples/your_example/
├── README.md              # What, why, how
├── your_healer.py         # Implementation
├── test_your_healer.py    # Tests (pytest)
├── config.toml            # Example config
├── sample_docs/           # Test data (optional)
│   └── *.md
└── demo.sh                # Interactive demo (optional)
```

---

## Resources

- **Template**: `../templates/custom_healer_template.py`
- **Guide**: `../docs/CUSTOM_HEALERS.md`
- **Base Classes**: `../guardian/core/base.py`
- **Confidence Model**: `../guardian/core/confidence.py`
- **Built-in Healers**: `../guardian/healers/`

---

**Last Updated**: 2026-01-11
