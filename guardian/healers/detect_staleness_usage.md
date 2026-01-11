# Detect Staleness Healer - Usage Guide

## Overview

The `DetectStalenessHealer` detects and fixes stale documentation by:
1. Auto-updating timestamps that are > N days behind git history
2. Flagging deprecated command syntax for manual review

## Configuration

```python
config = {
    'healers': {
        'detect_staleness': {
            # Days before considering timestamp stale
            'staleness_threshold_days': 30,

            # Timestamp patterns to recognize
            'timestamp_patterns': [
                r'\*\*Last Updated\*\*:\s*(\d{4}-\d{2}-\d{2})',
                r'Last updated:\s*(\d{4}-\d{2}-\d{2})',
                # Add more patterns as needed
            ],

            # Directories to skip during scanning
            'exclude_dirs': ['.git', 'node_modules', 'venv', 'dist', 'build'],

            # Deprecated command patterns to detect
            'deprecated_patterns': [
                {
                    'pattern': r'docker-compose\s+',
                    'message': 'Use docker compose (V2) instead',
                    'confidence': 0.95,
                    'suggestion': 'docker compose'
                },
                # Add more patterns as needed
            ]
        }
    }
}
```

## Usage

### Basic Check (Dry Run)

```python
from guardian.healers.detect_staleness import DetectStalenessHealer

healer = DetectStalenessHealer(config)
report = healer.check()

print(f"Issues found: {report.issues_found}")
print(f"Proposed changes: {len(report.changes)}")

for change in report.changes:
    print(f"  {change.file}:{change.line} - {change.reason}")
```

### Auto-Fix (Apply Changes)

```python
# Fix only high-confidence issues (>= 0.95)
report = healer.heal(min_confidence=0.95)

print(f"Issues fixed: {report.issues_fixed}/{report.issues_found}")
print(f"Success rate: {report.success_rate * 100:.1f}%")
```

### Custom Deprecated Patterns

```python
# Add project-specific deprecated patterns
config['healers']['detect_staleness']['deprecated_patterns'] = [
    {
        'pattern': r'make\s+build',
        'message': 'Use npm run build instead',
        'confidence': 0.90,
        'suggestion': 'npm run build'
    },
    {
        'pattern': r'python\s+setup\.py',
        'message': 'Use pip install instead of setup.py',
        'confidence': 0.85,
        'suggestion': 'pip install .'
    }
]
```

## Confidence Scoring

- **1.0 (100%)**: Timestamp updates (exact format match from git)
- **0.95**: Critical deprecated patterns (e.g., sudo pip)
- **0.85**: Common deprecated patterns (e.g., virtualenv)
- **0.80**: Style preference patterns (e.g., git checkout -b)

## Output Format

### HealingReport

```python
HealingReport(
    healer_name='DetectStalenessHealer',
    mode='heal',  # or 'check'
    timestamp='2026-01-11T12:00:00',
    issues_found=10,
    issues_fixed=8,
    changes=[...],  # List of Change objects
    errors=[...],  # List of error messages
    execution_time=1.23
)
```

### Change Object

```python
Change(
    file=Path('docs/guide.md'),
    line=3,
    old_content='**Last Updated**: 2025-01-01',
    new_content='**Last Updated**: 2026-01-11',
    confidence=1.0,
    reason='Timestamp 41 days behind git history (2025-01-01 → 2026-01-11)',
    healer='DetectStalenessHealer'
)
```

## Git Integration

The healer uses `git log` to determine when files were last modified:

```bash
git log -1 --format=%ai -- path/to/file.md
```

Files must be tracked by git for staleness detection to work.

## Timestamp Formats Supported

Default patterns (configurable):
- `**Last Updated**: YYYY-MM-DD`
- `**Last Updated**: YYYY-MM-DD HH:MM:SS`
- `Last updated: YYYY-MM-DD`
- `_Last modified: YYYY-MM-DD_`
- `Last Updated: YYYY-MM-DD` (without bold)

## Example Workflow

```python
from guardian.healers.detect_staleness import DetectStalenessHealer

# 1. Load config
config = load_config()  # Your config loading logic

# 2. Create healer
healer = DetectStalenessHealer(config)

# 3. Check for issues
check_report = healer.check()

if check_report.issues_found == 0:
    print("✓ All documentation is up to date")
else:
    print(f"⚠ Found {check_report.issues_found} stale items")

    # 4. Auto-fix high-confidence issues
    heal_report = healer.heal(min_confidence=0.95)

    print(f"✓ Fixed {heal_report.issues_fixed} issues")

    # 5. Manual review for lower-confidence issues
    manual_review = [
        c for c in check_report.changes
        if c.confidence < 0.95
    ]

    print(f"⚠ {len(manual_review)} issues need manual review")
```

## Notes

- **No TCF-specific paths**: All paths are configurable via `config` dict
- **Git required**: File staleness detection requires git history
- **Unicode safe**: Handles encoding errors gracefully
- **Commit strategy**: Timestamp updates are auto-committed per file
- **Deprecated commands**: Flagged for manual review (lower confidence)
