# Doc Guardian Architecture

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| Zero external deps | Python 3.8+ stdlib only (pathlib, dataclasses, typing, subprocess) |
| Config-driven | TOML/YAML/JSON - same codebase for any project type |
| Fail-safe | Validate before write, git-based rollback |
| Auditable | Every change tracked with file, line, reason, confidence |
| Extensible | Drop `my_healer.py` in `guardian/healers/`, add to config |

---

## System Overview

```
heal.py → HealingSystem (check/heal/validate/apply/rollback) → Healers → Utilities
```

**CLI**:
```bash
python guardian/heal.py --config config.toml --check    # Dry run
python guardian/heal.py --config config.toml --heal     # Apply fixes
python guardian/heal.py --config config.toml --list     # Show healers
```

---

## Core Data Structures

```python
@dataclass
class Change:
    file: Path           # File to modify
    line: int            # Line number (0 if not line-specific)
    old_content: str     # Content to replace
    new_content: str     # Replacement content
    confidence: float    # 0.0-1.0
    reason: str          # Human-readable explanation
    healer: str          # Healer name

@dataclass
class HealingReport:
    healer_name: str
    mode: str            # "check" or "heal"
    timestamp: str
    issues_found: int
    issues_fixed: int
    changes: List[Change]
    errors: List[str]
    execution_time: float
```

---

## Plugin Discovery

Healers auto-discovered from `guardian/healers/*.py`:

```python
# heal.py
for file in healer_dir.glob('*.py'):
    if file.stem.startswith('_'): continue
    module = importlib.import_module(f'guardian.healers.{file.stem}')
    # Find HealingSystem subclasses
```

---

## Safety: Validate → Apply → Rollback

```python
def heal(self, min_confidence: float = 0.9) -> HealingReport:
    for change in report.changes:
        if change.confidence < min_confidence: continue
        if not self.validate_change(change): continue
        if self.apply_change(change):
            applied.append(change)
        else:
            self.rollback_change(change)
```

**Path containment**:
```python
def validate_path_contained(path: Path, root: Path) -> Path:
    if not path.resolve().is_relative_to(root.resolve()):
        raise PathSecurityError(f"Path outside project root")
```

**Command injection prevention**:
```python
def safe_git_path(path: Path) -> str:
    if str(path).startswith('-'):
        return './' + str(path)
```

**File size limit**: 10 MB max

---

## Directory Structure

```
guardian/
  core/
    base.py           # HealingSystem, Change, HealingReport
    confidence.py     # Scoring model
    security.py       # Path validation, injection prevention
    git_utils.py      # Git operations
  healers/
    fix_broken_links.py
    detect_staleness.py
    resolve_duplicates.py
    ...
  heal.py             # Orchestrator
  install.py          # Git hook installation
  rollback.py         # Interactive rollback
```

---

## Custom Healer Template

```python
from guardian.core.base import HealingSystem, HealingReport, Change

class MyCustomHealer(HealingSystem):
    def check(self) -> HealingReport:
        changes = []
        for doc_file in self.doc_root.rglob('*.md'):
            if self._has_issue(doc_file):
                changes.append(self._create_fix(doc_file))
        return self.create_report(mode="check", changes=changes, ...)

    def heal(self, min_confidence=None) -> HealingReport:
        threshold = min_confidence or self.min_confidence
        report = self.check()
        applied = [c for c in report.changes
                   if c.confidence >= threshold
                   and self.validate_change(c)
                   and self.apply_change(c)]
        return self.create_report(mode="heal", changes=applied, ...)
```

---

## Performance

- **Parallel execution**: Independent healers run via `ProcessPoolExecutor`
- **Dependency ordering**: `sync_canonical` → `fix_broken_links` → `balance_references`
- **Incremental**: Only process files modified since last run (optional)

---

## Related Docs

- [CUSTOMIZATION.md](CUSTOMIZATION.md) - Project-specific configs
- [CONFIG_GUIDE.md](CONFIG_GUIDE.md) - All config options
- [CUSTOM_HEALER_QUICKSTART.md](CUSTOM_HEALER_QUICKSTART.md) - 5-min healer guide
- [CONFIDENCE_MODEL.md](CONFIDENCE_MODEL.md) - Confidence scoring details
