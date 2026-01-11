# Validation Framework

Validation stages: Startup (config) -> Pre-change -> Post-change (optional).

## Config Validation

Required fields: `project.root`, `project.doc_root`

### Resource Limits

| Resource | Limit |
|----------|-------|
| Max patterns | 1,000 |
| Max pattern length | 10,000 chars |
| Max path length | 4,096 chars |
| Max config nesting | 20 levels |
| Max array size | 10,000 items |

### Common Errors

```
Error: Config missing required key: 'project.root'
Fix:
[project]
root = "."
doc_root = "docs/"
```

```
Error: [confidence.auto_commit_threshold] Must be numeric, got string
Fix: auto_commit_threshold = 0.90  # Not "0.90"
```

```
Error: [project.doc_root] Path contains '..' (directory traversal not allowed)
Fix: doc_root = "docs/"  # Relative path only
```

```
Error: Invalid regex pattern: unterminated character set
Fix: link_pattern = "\\[([^\\]]+)\\]\\(([^)]+)\\)"  # Escape brackets
```

## Path Validation

Checks: no null bytes, no newlines, <= 4096 chars, no `..`, within project root, no symlinks (default).

```python
from guardian.core.path_validator import validate_path_contained
validated = validate_path_contained(Path(user_input), project_root)  # Raises PathSecurityError if invalid
```

## Regex Validation (ReDoS Prevention)

Blocked patterns (cause catastrophic backtracking):
- `(.*?)+`, `(.+)+`, `(.*)+`, `(.+)*`, `(\w+)+`

Safe alternatives:
- Use atomic groups: `(?>...)`
- Use possessive quantifiers: `*+`, `++`
- Limit quantifier ranges: `{1,100}` instead of `+`

## Change Validation

Default checks in `validate_change()`:
1. File within project root (security)
2. File exists
3. File size <= 10MB (hardcoded limit in `security.py`)
4. Old content matches current file

```python
# Custom validation in healer
def validate_change(self, change: Change) -> bool:
    if not super().validate_change(change):
        return False
    # Add custom checks
    if not self._target_exists(change):
        self.log_error(f"Link target does not exist")
        return False
    return True
```

## Rollback

Uses git: `git checkout HEAD -- <file>`

Requirements: file tracked by git.

Manual fallback: `.doc-guardian/backups/<file>.backup`

---

**Last Updated**: 2026-01-11
