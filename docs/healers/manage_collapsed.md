# ManageCollapsedHealer

Universal healer for managing collapsible `<details>` sections in documentation.

## Purpose

Maintains collapsed sections by:
1. Generating helpful expand hints from content analysis
2. Maintaining search index keywords (optional)
3. Detecting unused/stale sections
4. Archiving with user approval

## When to Use

- Documentation uses `<details>` tags for progressive disclosure
- Want to help readers decide whether to expand sections
- Need to detect sections that are never used
- Want to maintain keyword discoverability for collapsed content

## Configuration

### Required Config Keys

```python
config = {
    'project': {
        'root': '/path/to/project',
        'doc_root': '/path/to/docs'
    },
    'confidence': {
        'auto_commit_threshold': 0.8,
        'auto_stage_threshold': 0.7
    },
    'reporting': {
        'output_dir': '/path/to/reports'
    },
    'healers': {
        'manage_collapsed': {
            'hint_strategy': 'summary',  # or 'first_sentence', 'keywords'
            'track_usage': False,
            'long_section_threshold': 500,
            'missing_keywords_threshold': 0.5,
            'stopwords': []  # optional custom stopwords
        }
    }
}
```

### Hint Generation Strategies

| Strategy | Description | Best For |
|----------|-------------|----------|
| `summary` | Count code blocks, commands, bullets | Technical docs with structured content |
| `first_sentence` | Extract first sentence | Narrative docs with clear intros |
| `keywords` | List most common keywords | Reference docs |

## Features

### 1. Expand Hint Generation

Converts generic summaries into helpful hints:

**Before:**
```html
<details>
<summary>Installation</summary>
Run these commands...
```

**After:**
```html
<details>
<summary>Installation (Expand to see: 5 commands)</summary>
Run these commands...
```

**Confidence**: 85% for specific hints, 70% for generic

### 2. Unused Section Detection

Flags sections that are never expanded (heuristic):

- Very long sections (>500 lines by default)
- Low confidence (50-60%) - weak signal, requires manual review

### 3. Keyword Extraction

Extracts keywords from collapsed content for search indexing:

- Filters stopwords
- Minimum word length: 3 characters
- Lowercase normalization

## Usage

### Check Mode (Dry Run)

```python
from guardian.healers.manage_collapsed import ManageCollapsedHealer

healer = ManageCollapsedHealer(config)
report = healer.check()

print(f"Found {report.issues_found} issues")
for change in report.changes:
    print(f"{change.file}:{change.line} - {change.reason}")
```

### Heal Mode (Apply Fixes)

```python
report = healer.heal(min_confidence=0.8)
print(f"Fixed {report.issues_fixed}/{report.issues_found} issues")
```

### Custom Confidence Threshold

```python
# Only apply very confident changes
report = healer.heal(min_confidence=0.9)
```

## Examples

See `examples/manage_collapsed_example.py` for complete working example.

## HTML Pattern

Detects this pattern:

```html
<details>
<summary>Section Title</summary>

Content here...

</details>
```

## Confidence Scoring

| Hint Type | Confidence |
|-----------|-----------|
| Specific (code examples, commands) | 85% |
| Generic (character count) | 70% |
| Unused detection | 50-60% |

## Validation Rules

Before applying changes, validates:
1. File exists
2. Old content matches current file
3. New content is non-empty (unless explicit deletion)

## Output Format

```python
HealingReport(
    healer_name='ManageCollapsedHealer',
    mode='heal',
    timestamp='2026-01-11T12:00:00',
    issues_found=3,
    issues_fixed=2,
    changes=[Change(...)],
    errors=[],
    execution_time=0.12
)
```

## Limitations

1. **Unused detection is heuristic** - requires manual review
2. **No actual usage tracking** - relies on section length as proxy
3. **Simple keyword extraction** - no NLP/semantic analysis

## Future Enhancements

- [ ] Integration with analytics to track actual usage
- [ ] Detect deprecated content references
- [ ] Cross-reference checking (find sections referenced elsewhere)
- [ ] Archive workflow implementation
- [ ] Support for nested `<details>` tags

## Related

- Base class: `guardian.core.base.HealingSystem`
- See `tests/test_manage_collapsed.py` for test examples
