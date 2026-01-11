# Sync Canonical Healer

**Universal healer for syncing canonical source data to documentation.**

Extracted from TCF's `auto_sync_canonical.py` and generalized for any project.

## Purpose

When you have a canonical source file (JSON/YAML/TOML) that defines your project's vocabulary, specifications, or configuration, you need to keep documentation synchronized with it. This healer:

1. **Detects changes** to canonical source via git diff
2. **Identifies affected docs** based on configured patterns
3. **Renders updates** using Jinja2 templates
4. **Applies changes** with confidence-based auto-commit
5. **Creates backups** before modifying files

## When to Use

- **Vocabulary management**: Sync term definitions to reference docs
- **API documentation**: Sync schema to API reference pages
- **Configuration docs**: Keep config documentation aligned with actual config
- **Code generation**: Generate classifier/validator code from canonical data

## Configuration

See `examples/sync_canonical_config.yaml` for complete example.

### Required Fields

```yaml
healers:
  sync_canonical:
    enabled: true
    source_file: path/to/canonical.json  # Relative to project root
    source_format: json                   # json, yaml, or toml
    templates_dir: .doc-guardian/templates
    target_patterns:
      - file: docs/reference.md
        template: reference.md.j2
        sections: [all]
        full_replace: true
```

### Optional Fields

```yaml
healers:
  sync_canonical:
    backup_dir: .doc-guardian/backups     # Default shown
    context_builder: myproject.utils.build_context  # Python path to function
```

## Target Patterns

### Full File Replacement

Replace entire file with template output:

```yaml
- file: src/generated/terms.py
  template: classifier.py.j2
  sections: [all]
  full_replace: true
```

### Partial Section Replacement

Replace only a marked section within a file:

```yaml
- file: docs/skills/extraction.md
  template: model_codes_section.md.j2
  sections: [model_codes]
  section_pattern: "<!-- SYNC_START -->.*?<!-- SYNC_END -->"
  partial_template: model_codes_partial.md.j2
```

**Markers in target file:**

```markdown
# My Documentation

<!-- SYNC_START -->
This content will be replaced
<!-- SYNC_END -->

Manual content stays here.
```

## Template Context

Templates receive a `data` variable containing parsed canonical source, plus `timestamp`.

### Default Context

```python
{
    "timestamp": "2025-01-11 12:34:56",
    "data": {...}  # Parsed canonical source
}
```

### Custom Context Builder

For complex transformations, provide a Python function:

```python
# myproject/utils.py
from guardian.healers.sync_canonical import CanonicalLoader

def build_template_context(loader: CanonicalLoader) -> dict:
    """Build custom template context."""
    data = loader.load()

    return {
        'timestamp': datetime.now().isoformat(),
        'fan_types': data['metadata']['fan_types'],
        'model_codes': [k for k, v in data['terms'].items()
                        if v.get('type') == 'model'],
        # Custom transformations here
    }
```

Then reference it in config:

```yaml
context_builder: myproject.utils.build_template_context
```

## Template Examples

### Python Code Generation

See `examples/templates/classifier.py.j2`:

```jinja
VALID_VALUES = {{ data.valid_values | tojson }}

ALIASES = {
{%- for alias, canonical in data.aliases.items() %}
    "{{ alias }}": "{{ canonical }}",
{%- endfor %}
}
```

### Markdown Section

See `examples/templates/model_codes_section.md.j2`:

```jinja
<!-- SYNC_START -->
## Model Codes

{%- for code in data.model_codes | sort %}
- `{{ code }}` → {{ data.code_mapping[code] }}
{%- endfor %}
<!-- SYNC_END -->
```

## Confidence Scoring

Changes are scored 0.0 to 1.0 based on:

| Factor | Weight | Description |
|--------|--------|-------------|
| Sync markers | 30% | File has `<!-- SYNC_START -->` markers or is full_replace |
| Template rendered | 20% | Template compiled without errors |
| Structure preserved | 20% | Key markers (headers, code blocks) still present |
| No manual edits | 15% | No `# MANUAL EDIT` markers |
| Reasonable diff | 15% | Less than 500 line difference |

**Auto-commit threshold**: 0.90 (configurable via `confidence.auto_commit_threshold`)

## Preventing Auto-Sync

Add marker to files that should not be auto-synced:

```python
# MANUAL EDIT - Do not auto-sync this file
# or
<!-- MANUAL --> This section has custom edits
```

## Backup Strategy

Before modifying any file, healer creates timestamped backup:

```
.doc-guardian/backups/
  reference.md.20250111_123456.bak
  classifier.py.20250111_123457.bak
```

Backups are never automatically deleted.

## Usage

### Check Mode (Preview)

```python
from guardian.healers.sync_canonical import SyncCanonicalHealer

healer = SyncCanonicalHealer(config)
report = healer.check()

print(f"Found {report.issues_found} files needing sync")
for change in report.changes:
    print(f"  {change.file}: {change.confidence:.0%} confidence")
```

### Heal Mode (Apply Changes)

```python
report = healer.heal()  # Auto-commits changes ≥90% confidence

print(f"Synced {report.issues_fixed} of {report.issues_found} files")
```

### Custom Confidence Threshold

```python
report = healer.heal(min_confidence=0.95)  # Only ≥95% confidence
```

## Source Format Support

### JSON (stdlib)

```yaml
source_file: data/canonical.json
source_format: json
```

### YAML (requires PyYAML)

```yaml
source_file: data/canonical.yaml
source_format: yaml
```

Install: `pip install pyyaml`

### TOML (Python 3.11+ stdlib, else configparser)

```yaml
source_file: data/canonical.toml
source_format: toml
```

Python 3.11+ uses `tomllib` (no install needed).
Python <3.11 falls back to `configparser` (limited TOML support).

## Git Integration

### Change Detection

Healer uses git diff to detect which fields changed:

```python
changed_fields = detector.detect_changes(commit="HEAD")
# Returns: [ChangedField(field="fan_types", change_type="modified"), ...]
```

### Uncommitted Changes

Check if canonical source has uncommitted changes:

```python
has_changes = detector.has_uncommitted_changes()
```

## Error Handling

Errors are logged but non-fatal. Check report:

```python
report = healer.heal()

if report.has_errors:
    print("Errors encountered:")
    for error in report.errors:
        print(f"  - {error}")
```

## Comparison: TCF vs Universal

| Feature | TCF Implementation | Universal Version |
|---------|-------------------|-------------------|
| Source file | Hardcoded `unified_master.json` | Configurable via `source_file` |
| Format | JSON only | JSON/YAML/TOML |
| Templates | Hardcoded paths | Configurable `templates_dir` |
| Targets | Hardcoded `CANONICAL_MAPPINGS` | Configurable `target_patterns` |
| Context | TCF-specific ontology methods | Generic + custom context builder |
| Confidence | Fixed thresholds | Configurable thresholds |

## Known Limitations

1. **Template engine required**: Jinja2 must be installed (`pip install jinja2`)
2. **Git required**: Change detection uses git diff
3. **Regex patterns**: `section_pattern` must be valid regex (use raw strings in YAML)
4. **No merge conflicts**: If target file has uncommitted changes, sync may fail
5. **No rollback UI**: Backups are manual (no automatic rollback on error)

## Future Enhancements

- [ ] Support for multiple canonical sources
- [ ] Dependency graph (sync order based on dependencies)
- [ ] Dry-run diff preview
- [ ] Interactive approval UI
- [ ] Rollback command
- [ ] Conflict resolution strategies

## See Also

- `examples/sync_canonical_config.yaml` - Full configuration example
- `examples/templates/` - Template examples
- `guardian/core/base.py` - Base healer classes
- TCF's original implementation: `.claude/healing/auto_sync_canonical.py`
