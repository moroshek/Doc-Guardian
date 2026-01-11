# CLI Reference

**Last Updated**: 2026-01-11

---

## heal.py

Main healing orchestrator.

### Commands

| Command | Description |
|---------|-------------|
| `--check` | Analyze without modifying (default) |
| `--heal` | Apply fixes above confidence threshold |
| `--list` | List healers and execution order |
| `--validate-only` | Validate config, exit 0 (valid) or 1 (invalid) |

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--config PATH` | path | **Required** | Config file (TOML/YAML/JSON) |
| `--min-confidence` | float | from config | Override confidence threshold |
| `--skip` | string | - | Skip healers (comma-separated) |
| `--only` | string | - | Run single healer only |
| `--verbose` | flag | false | Detailed progress output |
| `--parallel` | flag | false | Run independent healers in parallel |
| `--max-workers` | int | min(cpu, 4) | Max parallel workers |
| `--continue-on-error` | flag | false | Continue if healer fails |
| `--strict` | flag | false | Exit 1 if any issues found |
| `--output` | path | from config | Report output path |
| `--dry-run` | flag | false | Show changes without applying |

### Parallel Execution

The `--parallel` flag runs independent healers concurrently for faster execution.

**Healer Dependencies**:
- `sync_canonical` must run first (updates source data)
- `fix_broken_links` must complete before `balance_references`
- Other healers can run in parallel

**Default Order** (sequential):
1. sync_canonical
2. fix_broken_links
3. detect_staleness (can be parallel with #2)
4. resolve_duplicates (can be parallel with #2)
5. balance_references (depends on #2)
6. manage_collapsed (can be parallel)
7. enforce_disclosure (can be parallel)

**Memory**: Each worker process duplicates memory. Use `--max-workers 2` on systems with <4GB RAM.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Issues found (with `--strict`) or errors |

### Examples

```bash
# Check for issues
python guardian/heal.py --config config.toml --check

# Heal with high confidence
python guardian/heal.py --config config.toml --heal --min-confidence 0.95

# Single healer only
python guardian/heal.py --config config.toml --heal --only fix_broken_links

# CI/CD: fail if issues
python guardian/heal.py --config config.toml --check --strict --verbose

# Dry run
python guardian/heal.py --config config.toml --heal --dry-run --verbose
```

---

## install.py

Git hooks installer.

### Commands

| Command | Description |
|---------|-------------|
| (default) | Install all configured hooks |
| `--list` | List hooks and installation status |
| `--uninstall` | Remove hooks, restore backups |
| `--version` | Show hook template version |

### Options

| Flag | Type | Description |
|------|------|-------------|
| `--hook NAME` | string | Specific hook (`post-commit`, `pre-push`) |
| `--force` | flag | Overwrite existing (backs up files, removes symlinks) |
| `--dry-run` | flag | Preview without changes |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Partial success |
| 2 | Failed |
| 3 | Not in git repo |
| 4 | Guardian directory not found |

### Examples

```bash
# Install all hooks
python guardian/install.py

# Install specific hook
python guardian/install.py --hook post-commit

# Preview installation
python guardian/install.py --dry-run

# Show hook version
python guardian/install.py --version
# Output: Doc Guardian hook template version: 1.1.0

# Uninstall
python guardian/install.py --uninstall
```

---

## Git Hooks

### post-commit

- Runs `heal.py --heal --min-confidence 0.90` after commits
- Non-blocking (exit 0 even on failure)
- Skip: `git commit --no-verify`

### pre-push

- Runs `heal.py --check --verbose` before push
- **Blocks push if issues found**
- Skip: `git push --no-verify`

Config search order:
1. `$PROJECT_ROOT/config.toml`
2. `$PROJECT_ROOT/doc-guardian.toml`
3. `$PROJECT_ROOT/.doc-guardian/config.toml`
4. `$GUARDIAN_DIR/../config.toml`

**If no config found**: Hook exits with code 4 (EXIT_NO_GUARDIAN) and logs error to stderr.

---

## rollback.py

Rollback healing changes using git revert or backup restoration.

### Commands

| Command | Description |
|---------|-------------|
| (default) | Interactive mode - select from recent commits |
| `--show` | Show recent healing commits |
| `--commit HASH` | Revert specific commit |
| `--last [N]` | Revert last N healing commits (default: 1) |
| `--backup FILE` | Restore from backup file |

### Options

| Flag | Type | Description |
|------|------|-------------|
| `--commit` | string | Specific commit hash to revert |
| `--last` | int | Revert last N commits (default: 1) |
| `--backup` | path | Backup file to restore from |
| `--target` | path | Target file for backup restore |
| `--no-edit` | flag | Don't prompt for confirmation |
| `--pattern` | string | Git grep pattern (default: 'docs') |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Failed or not in git repo |

### Examples

```bash
# Interactive mode (select commit to revert)
python guardian/rollback.py

# Show recent healing commits
python guardian/rollback.py --show

# Revert specific commit
python guardian/rollback.py --commit abc123

# Revert last healing commit
python guardian/rollback.py --last

# Revert last 3 healing commits
python guardian/rollback.py --last 3

# Restore from backup file
python guardian/rollback.py --backup README.md.backup --target README.md

# Non-interactive revert
python guardian/rollback.py --last --no-edit
```

---

## CI/CD Workflow

```bash
# Validate (fail build if issues)
python guardian/heal.py --config config.toml --check --strict --verbose

# Auto-fix high confidence
python guardian/heal.py --config config.toml --heal --min-confidence 0.99

# Re-validate
python guardian/heal.py --config config.toml --check --strict
```

---

## See Also

- [Configuration Reference](CONFIGURATION.md)
- [API Reference](API.md)
