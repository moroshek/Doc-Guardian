# Configuration Guide

Quick reference for configuring `doc-guardian`.

## Quick Start

```bash
# Copy template to create your config
cp config.toml.template config.toml

# Edit to customize for your project
vim config.toml
```

## Essential Settings

### 1. Project Basics

```toml
[project]
name = "my-project"
root = "."
doc_root = "docs/"
```

### 2. Confidence Thresholds

```toml
[confidence]
auto_commit_threshold = 0.90    # Auto-commit if ≥90% confident
auto_stage_threshold = 0.80     # Auto-stage if ≥80% confident
report_only_threshold = 0.50    # Only report if ≥50% confident
```

**Lower thresholds** = More automation (riskier)  
**Higher thresholds** = More manual review (safer)

### 3. Enable Healers

```toml
[healers.fix_broken_links]
enabled = true                  # Enable this healer

[healers.sync_canonical]
enabled = false                 # Disable this healer
```

## Healer Overview

| Healer | Default | Requires Setup | Description |
|--------|---------|----------------|-------------|
| `fix_broken_links` | ✓ ON | No | Repairs broken internal links |
| `detect_staleness` | ✓ ON | No | Flags outdated docs |
| `resolve_duplicates` | ✓ ON | No | Finds duplicate content |
| `balance_references` | ✗ OFF | No | Ensures bidirectional links |
| `manage_collapsed` | ✗ OFF | Yes | Collapses long sections |
| `sync_canonical` | ✗ OFF | Yes | Syncs from schema files |
| `enforce_disclosure` | ✗ OFF | Yes | Enforces layer architecture |

## Common Configurations

### Conservative (Manual Review)

```toml
[confidence]
auto_commit_threshold = 0.95
auto_stage_threshold = 0.90
report_only_threshold = 0.70

[git]
auto_commit = false
```

### Aggressive (Full Automation)

```toml
[confidence]
auto_commit_threshold = 0.80
auto_stage_threshold = 0.70
report_only_threshold = 0.50

[git]
auto_commit = true
```

### First-Time Setup

```toml
[advanced]
dry_run = true                  # Analyze but don't modify

[reporting]
verbose = true                  # Detailed logging
```

## Advanced Features

### Custom Deprecated Patterns

```toml
[healers.detect_staleness]
deprecated_patterns = [
    'python2\s+',               # Python 2
    'npm\s+install\s+-g',       # Global npm
    # Add your own patterns
]
```

### Hierarchy Rules for Duplicates

```toml
[healers.resolve_duplicates]
hierarchy_rules = [
    "README.md",                # Keep this version
    "docs/index.md",            # Then this
    "docs/",                    # Then any docs
]
```

### Progressive Disclosure Layers

```toml
[healers.enforce_disclosure.layers.overview]
max_lines = 50
allowed_depth = 2
file_patterns = ["README.md"]
```

## Validation

Test your configuration:

```bash
# Validate TOML syntax
python3 -c "import tomllib; tomllib.load(open('config.toml', 'rb'))"

# Run doc-guardian in dry-run mode
doc-guardian --dry-run
```

## See Also

- [config.toml.template](config.toml.template) - Full template with all options
- [PRD](PRD.md) - Complete specification
- [README](README.md) - Usage guide
