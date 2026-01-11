# Guardian Core Framework

Universal base classes for documentation healing systems, extracted from TCF's healing patterns.

## Overview

This framework provides config-driven abstractions that are:
- **Universal** - No project-specific paths or logic
- **Stdlib-only** - Zero external dependencies (except optional PyYAML)
- **Well-documented** - Complete docstrings and type hints
- **Battle-tested** - Patterns extracted from production TCF healers

## Modules

### base.py
Core abstractions for healing systems:
- `Change` - Dataclass representing a proposed change
- `HealingReport` - Dataclass for operation results
- `HealingSystem` - Abstract base class with check/heal/validate/apply/rollback methods

### confidence.py
Multi-factor confidence scoring:
- `ConfidenceFactors` - 4-factor model (pattern/magnitude/risk/history)
- `calculate_confidence()` - Weighted scoring (0.0-1.0)
- `get_action_threshold()` - Determine auto_commit/auto_stage/report_only

### validation.py
Validation utilities:
- `validate_syntax()` - MD/JSON/YAML/Python syntax checking
- `validate_links()` - Internal link existence verification
- `validate_change()` - Change safety validation
- `validate_all_changes()` - Batch validation

### git_utils.py
Git integration:
- `rollback_file()` - Restore file using git checkout
- `git_add()` - Stage file for commit
- `git_commit()` - Commit with standard format
- `git_status_clean()` - Check for uncommitted changes

### reporting.py
Report generation:
- `generate_markdown_report()` - Human-readable format
- `generate_json_report()` - Machine-readable format
- `generate_console_output()` - Terminal-friendly with colors
- `save_report()` - Write to disk

## Quick Start

```python
from guardian.core import HealingSystem, HealingReport, Change
from pathlib import Path

class MyHealer(HealingSystem):
    def check(self) -> HealingReport:
        # Detect issues
        changes = []
        # ... analyze files, create Change objects ...
        
        return self.create_report(
            mode="check",
            issues_found=len(changes),
            issues_fixed=0,
            changes=changes,
            execution_time=1.23
        )
    
    def heal(self, min_confidence=None) -> HealingReport:
        # Get proposed changes
        report = self.check()
        
        # Apply high-confidence changes
        threshold = min_confidence or self.min_confidence
        fixed = 0
        
        for change in report.changes:
            if change.confidence >= threshold:
                if self.validate_change(change):
                    if self.apply_change(change):
                        fixed += 1
        
        return self.create_report(
            mode="heal",
            issues_found=len(report.changes),
            issues_fixed=fixed,
            changes=report.changes,
            execution_time=2.45
        )

# Usage
config = {
    'project': {
        'root': '/path/to/project',
        'doc_root': '/path/to/docs'
    },
    'confidence': {
        'auto_commit_threshold': 0.90,
        'auto_stage_threshold': 0.80
    },
    'reporting': {
        'output_dir': '.guardian/reports'
    }
}

healer = MyHealer(config)
report = healer.check()
print(f"Found {report.issues_found} issues")
```

## Confidence Model

4-factor weighted scoring:
- **Pattern Match** (40%) - How well detected pattern matches known patterns
- **Change Magnitude** (30%) - Size of change (smaller = higher confidence)
- **Risk Assessment** (20%) - Risk level (lower risk = higher confidence)
- **Historical Accuracy** (10%) - Past success rate for this type

Thresholds:
- ≥90% → `auto_commit` - Changes committed automatically
- ≥80% → `auto_stage` - Changes staged for review
- <80% → `report_only` - Changes reported only

## Dependencies

**Required**: Python 3.8+ stdlib only
- `pathlib`, `dataclasses`, `abc`, `typing`, `json`, `re`, `subprocess`, `datetime`

**Optional**:
- `PyYAML` - For YAML syntax validation (gracefully degrades if missing)

## Design Principles

1. **Config-driven** - All paths and thresholds from config
2. **Validation-first** - Validate before applying changes
3. **Reversible** - Git integration for safe rollback
4. **Observable** - Comprehensive reporting at each step
5. **Composable** - Small, focused utilities that combine well

## Patterns Extracted from TCF

| Pattern | TCF Source | Universal Abstraction |
|---------|------------|----------------------|
| Healer result tracking | `HealerResult` dataclass | `HealingReport` |
| Change proposals | `BrokenLink.suggested_fix` | `Change` dataclass |
| Confidence scoring | `calculate_confidence()` | `ConfidenceFactors` + `calculate_confidence()` |
| Validation | `LinkValidator.validate()` | `validate_change()` |
| Git operations | `rollback_file()`, `git_commit()` | `git_utils` module |
| Reporting | `generate_report()` methods | `reporting` module |

## Anti-Patterns Avoided

- ❌ Hardcoded paths (`/home/moroshek/TCF` → config-driven)
- ❌ Project-specific logic (TCF fan types → generic patterns)
- ❌ Heavy dependencies (Jinja2 → stdlib only)
- ❌ Implicit behavior (always explicit via config)
- ❌ Globals (PROJECT_ROOT → instance config)

## Next Steps

See parent directory for:
- `config/` - Configuration schema and defaults
- `healers/` - Concrete healer implementations
- `templates/` - Report and output templates
