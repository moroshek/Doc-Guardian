# Git Integration

## Hooks

| Hook | Trigger | Purpose | Blocking |
|------|---------|---------|----------|
| post-commit | After commit | Auto-heal (>= 0.90 confidence) | No |
| pre-push | Before push | Validate docs | Yes |

## Installation

```bash
python doc-guardian/guardian/install.py              # Install both
python doc-guardian/guardian/install.py --hook post-commit  # Specific hook
python doc-guardian/guardian/install.py --dry-run    # Preview
python doc-guardian/guardian/install.py --list       # Check status
python doc-guardian/guardian/install.py --force      # Overwrite existing (backs up)
python doc-guardian/guardian/install.py --uninstall  # Remove hooks
```

## Config File Locations (search order)

1. `$PROJECT_ROOT/config.toml`
2. `$PROJECT_ROOT/doc-guardian.toml`
3. `$PROJECT_ROOT/.doc-guardian/config.toml`
4. `$GUARDIAN_DIR/../config.toml`

## Bypass Hooks

```bash
git commit --no-verify -m "WIP"
git push --no-verify
```

Disable permanently:
```bash
rm .git/hooks/post-commit
git config core.hooksPath /dev/null  # Disable all hooks
```

## CI/CD

### GitHub Actions

```yaml
- name: Validate Documentation
  run: |
    pip install -r doc-guardian/requirements.txt
    python doc-guardian/guardian/heal.py --config config.toml --check --verbose
```

### GitLab CI

```yaml
doc-validation:
  image: python:3.11
  script:
    - pip install -r doc-guardian/requirements.txt
    - python doc-guardian/guardian/heal.py --config config.toml --check --verbose
  only:
    changes:
      - docs/**/*
```

### Pre-commit Framework

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: doc-guardian
        entry: python doc-guardian/guardian/heal.py
        args: ['--config', 'config.toml', '--check']
        language: system
        files: \.(md|rst|txt)$
```

## Manual Commands

```bash
python guardian/heal.py --config config.toml --check              # Detect issues
python guardian/heal.py --config config.toml --heal               # Apply fixes
python guardian/heal.py --config config.toml --heal --dry-run     # Preview
python guardian/heal.py --config config.toml --heal --min-confidence 0.95
```

---

**Last Updated**: 2026-01-11
