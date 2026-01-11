# Troubleshooting

## Configuration Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Config missing required key: 'project.root'` | Missing section | Add `[project]` with `root = "."` and `doc_root = "docs/"` |
| `Must be numeric, got string` | Quoted number | `auto_commit_threshold = 0.90` not `"0.90"` |
| `Invalid regex pattern` | Malformed regex | Test with `re.compile(pattern)` in Python |
| `Path contains '..'` | Directory traversal | Use relative path: `doc_root = "docs/"` |
| `Path does not exist` | Missing directory | `mkdir -p docs/` or correct path |
| `Config file is empty` | Zero bytes | `cp doc-guardian/config.example.toml config.toml` |

### YAML/TOML Parse Errors

| Issue | Fix |
|-------|-----|
| Wrong indentation (YAML) | Use 2-space indent under parent |
| Special chars in value | Quote: `pattern: "\\[Guide\\]:"` |
| Tabs in YAML | `expand -t 2 config.yaml > fixed.yaml` |
| Space in TOML section | `[healers.fix_broken_links]` not `[healers.broken links]` |
| Duplicate keys | Remove duplicate |

## Installation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Not in a git repository` | Outside repo | `cd /path/to/repo` or `git init` |
| `Guardian directory not found` | Wrong location | Install to `doc-guardian/guardian/` |
| `Cannot write to .git/hooks` | Permissions | `chmod u+w .git/hooks` |
| `Existing hook is symlink` | Managed by other tool | `--force` to remove or skip |

## Runtime Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `File does not exist` | Deleted file | Update references or restore file |
| `Old content not found` | File modified since detection | Re-run healer |
| `Path escapes project root` | Security violation | Validate paths before use |
| `Git is not installed` | Missing git | Install: `apt install git` / `brew install git` |
| `Cannot rollback untracked file` | Not in git | `git add <file>` or delete manually |
| `File too large: 15 MB` | Exceeds 10 MB limit | Exclude file in config |

## Security Errors

| Error | Module | Cause | Fix |
|-------|--------|-------|-----|
| `PathSecurityError: Path escapes allowed root` | path_validator | Path traversal attempt (`..`) | Use relative path within project |
| `RegexSecurityError: Nested quantifiers` | regex_validator | ReDoS pattern `(.+)+` | Simplify regex, avoid nested quantifiers |
| `RegexConfigError: Pattern is invalid` | regex_validator | Malformed regex | Test with `re.compile(pattern)` |
| `ValueError: File too large` | security | File > 10 MB | Exclude file or split it |
| `MemoryError: Too many items` | security | Collection > limit (e.g., >1000 patterns) | Reduce list size |

### ReDoS (Regex Denial of Service)

**Dangerous patterns**:
- `(.+)+` - Nested quantifiers
- `(a|a)+` - Overlapping alternation with quantifier
- `(.*)+` - Repeated wildcard capturing
- `.*` without anchors - Unanchored wildcards

**Safe alternatives**:
```toml
# Bad: Nested quantifiers
link_pattern = '(.+)+\.md'

# Good: Simple quantifier
link_pattern = '.+\.md'

# Bad: Overlapping alternation
deprecated_patterns = ['(foo|fo)+']

# Good: Non-overlapping
deprecated_patterns = ['foo+']
```

### Path Security

Doc Guardian rejects any path that escapes the project root:

```toml
# Bad: Directory traversal
doc_root = "../../../etc"

# Good: Relative within project
doc_root = "docs/"

# Bad: Absolute path outside project
source_file = "/etc/passwd"

# Good: Relative path
source_file = "schema.json"
```

## Hook Issues

| Problem | Check | Fix |
|---------|-------|-----|
| Hook not running | `ls -la .git/hooks/post-commit` | `python doc-guardian/guardian/install.py --force` |
| Permission denied | `ls -l .git/hooks/` | `chmod +x .git/hooks/*` |
| Config not found | Check locations | Create `config.toml` in project root |
| Hook blocking work | N/A | `git commit --no-verify` |
| Changes not applied | Run `--verbose` | Check confidence score, lower threshold |
| Recursive commits | Hook triggering itself | Add `grep -q "auto-heal"` check |
| pre-push blocks clean docs | Validation logic | Debug with `--check --verbose` |

## Performance

| Problem | Diagnostic | Fix |
|---------|------------|-----|
| Slow healing | `time python guardian/heal.py ...` | Exclude dirs, limit file size, optimize regex |
| High memory | `/usr/bin/time -v python ...` | `max_workers = 1`, exclude large files |
| Slow git hooks | N/A | `--no-verify`, disable expensive healers |

Exclusion config:
```toml
[project]
excluded_dirs = ["vendor/", "node_modules/", "archive/"]

[healers.fix_broken_links]
exclude_files = ["docs/large_file.md"]  # Note: max_file_size_mb is not implemented; limit is 10 MB
```

## Platform-Specific

### Windows

| Error | Fix |
|-------|-----|
| Permission denied | Run as admin or use WSL |
| UnicodeDecodeError | `$env:PYTHONIOENCODING="utf-8"` |
| Backslash paths | Use forward slashes: `doc_root = "docs/guides"` |

### macOS

| Error | Fix |
|-------|-----|
| `python: command not found` | Use `python3` or `alias python=python3` |
| Permission denied (Catalina+) | Keep in project dir, don't use `/usr/` |

### Linux

| Error | Fix |
|-------|-----|
| `No module named 'yaml'` | `pip3 install -r doc-guardian/requirements.txt` |
| `python3: No such file` | `apt install python3` |

## Quick Debug Commands

```bash
# Validation
python guardian/heal.py --config config.toml --check --verbose 2>&1 | tee debug.log

# Config check
python -c "
from guardian.core.config_validator import validate_and_load_config
from pathlib import Path
config, result = validate_and_load_config(Path('config.toml'))
print('Valid:', result.is_valid, 'Errors:', result.errors)
"

# File permissions
ls -la .git/hooks/ doc-guardian/guardian/

# TOML syntax
python -m toml config.toml
```

## Reset

```bash
python doc-guardian/guardian/install.py --uninstall
rm -rf .doc-guardian/
```

---

**Last Updated**: 2026-01-11
