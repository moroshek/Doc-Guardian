# API Reference

**Last Updated**: 2026-01-11

**Module**: `guardian`

---

## Core Classes

### HealingSystem

**Module**: `guardian.core.base`

Base class for all healers. Implements check -> heal -> validate workflow.

```python
from guardian.core.base import HealingSystem

class MyHealer(HealingSystem):
    def check(self) -> HealingReport: ...
    def heal(self, min_confidence: float = None) -> HealingReport: ...
```

| Method | Returns | Description |
|--------|---------|-------------|
| `check()` | `HealingReport` | Analyze docs, return issues |
| `heal(min_confidence=None)` | `HealingReport` | Apply fixes above threshold |
| `validate_change(change)` | `bool` | Check if change is safe |
| `apply_change(change)` | `bool` | Apply change (atomic write) |
| `rollback_change(change)` | `bool` | Undo applied change |

**Constructor Raises**: `KeyError`, `FileNotFoundError`, `NotADirectoryError`, `PathSecurityError`

---

### Change

**Module**: `guardian.core.base`

```python
@dataclass
class Change:
    file: Path           # File to modify
    line: int            # Line number (0 if not line-specific)
    old_content: str     # Content to replace
    new_content: str     # New content
    confidence: float    # 0.0-1.0
    reason: str          # Human-readable explanation
    healer: str          # Healer name
```

---

### HealingReport

**Module**: `guardian.core.base`

```python
@dataclass
class HealingReport:
    healer_name: str
    mode: str                        # "check" or "heal"
    timestamp: str                   # ISO format
    issues_found: int
    issues_fixed: int
    changes: List[Change] = []
    errors: List[str] = []
    execution_time: float = 0.0

    @property
    def success_rate(self) -> float  # issues_fixed / issues_found
    @property
    def has_errors(self) -> bool
```

---

## Healers

All inherit from `HealingSystem`. Config keys under `healers.<name>`.

| Class | Module | Config Section |
|-------|--------|----------------|
| `FixBrokenLinksHealer` | `guardian.healers.fix_broken_links` | `healers.fix_broken_links` |
| `DetectStalenessHealer` | `guardian.healers.detect_staleness` | `healers.detect_staleness` |
| `ResolveDuplicatesHealer` | `guardian.healers.resolve_duplicates` | `healers.resolve_duplicates` |
| `BalanceReferencesHealer` | `guardian.healers.balance_references` | `healers.balance_references` |
| `ManageCollapsedHealer` | `guardian.healers.manage_collapsed` | `healers.manage_collapsed` |
| `SyncCanonicalHealer` | `guardian.healers.sync_canonical` | `healers.sync_canonical` |
| `EnforceDisclosureHealer` | `guardian.healers.enforce_disclosure` | `healers.enforce_disclosure` |

**Example**:

```python
from guardian.healers.fix_broken_links import FixBrokenLinksHealer

config = {
    'project': {'root': '.', 'doc_root': 'docs/'},
    'healers': {'fix_broken_links': {'fuzzy_threshold': 0.8}}
}

healer = FixBrokenLinksHealer(config)
report = healer.check()
print(f"Found {report.issues_found} broken links")

report = healer.heal(min_confidence=0.9)
print(f"Fixed {report.issues_fixed} links")
```

---

## Utilities

### Confidence Scoring

**Module**: `guardian.core.confidence`

```python
def calculate_confidence(factors: ConfidenceFactors, weights: dict = None) -> float
def assess_change_magnitude(old_content: str, new_content: str) -> float
def assess_risk_level(file: Path, change_type: str) -> float
```

### Git Operations

**Module**: `guardian.core.git_utils`

```python
def is_git_repo(path: Path) -> bool
def get_git_root(path: Path) -> Optional[Path]
def stage_files(files: List[Path], git_root: Path) -> bool
def create_commit(message: str, git_root: Path, author: str = None) -> bool
```

### Reporting

**Module**: `guardian.core.reporting`

```python
def generate_markdown_report(report: HealingReport) -> str
def generate_json_report(report: HealingReport) -> str
```

### Path Validation

**Module**: `guardian.core.path_validator`

```python
def validate_path_contained(path: Path, allowed_root: Path, context: str = "path") -> Path
def validate_project_root(path: Path) -> Path
def validate_doc_root(doc_root: Path, project_root: Path) -> Path
```

**Raises**: `PathSecurityError`, `FileNotFoundError`, `NotADirectoryError`, `PermissionError`

### Regex Validation

**Module**: `guardian.core.regex_validator`

```python
def validate_regex_safety(pattern: str, context: str = "pattern", max_length: int = 10000) -> re.Pattern
```

**Raises**: `RegexSecurityError` (ReDoS), `RegexConfigError` (invalid)

### Security Utilities

**Module**: `guardian.core.security`

Core security utilities preventing memory exhaustion, command injection, and path leaks.

#### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_FILE_SIZE_BYTES` | 10 MB | Maximum file size for reading into memory |
| `MAX_FILES_PER_OPERATION` | 10,000 | Maximum files per operation |
| `MAX_CONTENT_BLOCKS` | 10,000 | Maximum blocks for duplication detection |
| `MAX_PATTERNS` | 1,000 | Maximum regex patterns from config |
| `MAX_LINKS_PER_FILE` | 5,000 | Maximum links to extract per file |

#### File Size Validation

```python
def validate_file_size(file_path: Path, max_size: int = MAX_FILE_SIZE_BYTES) -> Tuple[bool, Optional[str]]
def safe_read_file(file_path: Path, max_size: int = MAX_FILE_SIZE_BYTES, encoding: str = 'utf-8') -> str
def safe_read_bytes(file_path: Path, max_size: int = MAX_FILE_SIZE_BYTES) -> bytes
```

**Example**:

```python
from guardian.core.security import safe_read_file, validate_file_size

# Check before reading
is_valid, error = validate_file_size(Path("docs/large.md"))
if not is_valid:
    print(f"Skipping: {error}")

# Or use safe_read_file which validates automatically
try:
    content = safe_read_file(Path("docs/guide.md"))
except ValueError as e:
    print(f"File too large: {e}")
```

#### Git Path Safety

```python
def safe_git_path(path: Path) -> str
def validate_git_path(path: Path) -> Tuple[bool, Optional[str]]
```

Prevents command injection via malicious filenames starting with `-`.

**Example**:

```python
from guardian.core.security import safe_git_path

# Path "-rf ." would be interpreted as git option
safe_path = safe_git_path(Path("-rf ."))
# Returns "./-rf ." - safe for git commands
```

#### Module Whitelist

```python
def validate_module_path(module_path: str, allowed_modules: Set[str] = None) -> Tuple[bool, Optional[str]]
```

Validates that imported modules are in the allowed whitelist.

**Allowed Modules** (default):
- `guardian.core`, `guardian.core.base`, `guardian.core.confidence`, `guardian.core.reporting`
- `guardian.healers`
- `json`, `datetime`, `pathlib`, `collections`, `functools`, `itertools`, `operator`, `re`

#### Collection Limits

```python
def check_collection_size(collection, max_size: int, collection_name: str = "collection") -> Tuple[bool, Optional[str]]
def enforce_collection_limit(collection, max_size: int, collection_name: str = "collection")
```

**Raises**: `MemoryError` if collection exceeds limit (enforce_collection_limit only).

**Example - check_collection_size**:

```python
from guardian.core.security import check_collection_size, MAX_PATTERNS

# Validate list size before processing
config_patterns = config.get('patterns', [])
is_valid, error = check_collection_size(config_patterns, MAX_PATTERNS, 'patterns')
if not is_valid:
    raise ConfigError(f"Too many patterns: {error}")
```

**Example - enforce_collection_limit**:

```python
from guardian.core.security import enforce_collection_limit, MAX_PATTERNS

# Hard limit a list (raises MemoryError if exceeded)
user_patterns = get_user_input()
enforce_collection_limit(user_patterns, MAX_PATTERNS, 'user_patterns')
# Raises MemoryError if len(user_patterns) > MAX_PATTERNS
```

#### Error Sanitization

```python
def sanitize_error_message(message: str, project_root: Path = None) -> str
```

Sanitizes error messages to avoid leaking absolute paths.

**Example**:

```python
from guardian.core.security import sanitize_error_message
from pathlib import Path

# Remove sensitive paths from error messages
try:
    process_file(Path('/home/user/secret/config.toml'))
except Exception as e:
    # Original: "Failed to read /home/user/secret/config.toml"
    safe_msg = sanitize_error_message(str(e), project_root=Path('/home/user/secret'))
    # Result: "Failed to read <project>/config.toml"
    log_error(safe_msg)
```

---

## Configuration

**Module**: `guardian.heal`, `guardian.core.config_validator`

```python
def load_config_validated(config_path: Path) -> Tuple[Dict, ValidationResult]
def validate_config_schema(config: dict, project_root: Path = None, check_paths: bool = True) -> ValidationResult

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    validated_config: Dict[str, Any]

    def raise_if_invalid(): ...
    def log_warnings(): ...
```

---

## Complete Example

```python
from pathlib import Path
from guardian.heal import load_config_validated
from guardian.healers import FixBrokenLinksHealer, DetectStalenessHealer

config, result = load_config_validated(Path("config.toml"))
if not result.is_valid:
    print(result.errors)
    exit(1)

for healer_cls in [FixBrokenLinksHealer, DetectStalenessHealer]:
    healer = healer_cls(config)
    report = healer.check()
    if report.issues_found:
        report = healer.heal(min_confidence=0.9)
        print(f"{healer_cls.__name__}: fixed {report.issues_fixed}/{report.issues_found}")
```

---

## See Also

- [Configuration Reference](CONFIGURATION.md)
- [CLI Reference](CLI.md)
