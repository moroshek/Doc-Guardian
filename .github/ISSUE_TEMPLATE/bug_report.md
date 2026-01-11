---
name: Bug Report
about: Report a bug or unexpected behavior
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

A clear and concise description of what the bug is.

## Steps to Reproduce

1. Create config with '...'
2. Run command '...'
3. See error

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened.

## Error Output

```
Paste any error messages or unexpected output here
```

## Environment

- **OS**: [e.g., Ubuntu 22.04, macOS 14, Windows 11]
- **Python version**: [e.g., 3.11.2]
- **Doc Guardian version**: [e.g., commit hash or version]

## Configuration

```toml
# Paste relevant parts of your config.toml
[project]
name = "..."
doc_root = "..."

[healers.affected_healer]
enabled = true
```

## Sample Files

If relevant, include sample markdown/documentation files that trigger the bug:

```markdown
# Sample doc that causes the issue
[Broken link](path/that/fails.md)
```

## Additional Context

Add any other context about the problem here.

## Possible Fix

If you have ideas on how to fix this, share them here.
