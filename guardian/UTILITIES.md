# Doc Guardian Utilities

Utility scripts for installing git hooks and rolling back changes.

## install.py

Install git hooks that run healing automatically.

### Features

- **Auto-detection**: Finds git root and guardian directory automatically
- **Safety**: Backs up existing hooks before overwriting
- **Selective**: Install all hooks or specific ones
- **Status**: View which hooks are installed

### Usage

```bash
# List available hooks and their status
python guardian/install.py --list

# Install all hooks
python guardian/install.py

# Install specific hook
python guardian/install.py --hook post-commit

# Uninstall all hooks
python guardian/install.py --uninstall

# Force overwrite existing hooks (backs up old ones)
python guardian/install.py --force
```

### Hooks Installed

1. **post-commit**: Runs healing after each commit (non-blocking)
   - Heals high-confidence issues (≥0.90)
   - Does not block commits if healing fails

2. **pre-push**: Validates docs before push (blocking)
   - Runs full check with `--verbose`
   - Blocks push if validation fails
   - User can bypass with `git push --no-verify`

### Hook Templates

Hooks are shell scripts that:
- Auto-detect git root
- Find guardian directory
- Call `heal.py` with appropriate flags
- Handle errors gracefully

## rollback.py

Rollback healing changes using git or backup files.

### Features

- **Interactive mode**: Browse and select commits to revert
- **Commit search**: Find healing commits by pattern
- **Backup restore**: Restore files from backup copies
- **Safety**: Shows changes before reverting, prompts for confirmation

### Usage

```bash
# Interactive mode (select from recent commits)
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

# Auto-revert without prompts (for scripts)
python guardian/rollback.py --last --no-edit

# Search by custom pattern
python guardian/rollback.py --show --pattern "fix\|feat"
```

### How It Works

1. **Commit Detection**: Searches git log for commits with `[docs]` prefix
2. **File Analysis**: Shows which files will be affected by rollback
3. **Confirmation**: Prompts before making changes (unless `--no-edit`)
4. **Revert**: Uses `git revert` to create inverse commit
5. **Backup**: Preserves current state when restoring from backups

### Search Patterns

By default, rollback searches for commits with `[docs]` prefix. Customize with `--pattern`:

```bash
# Find commits with [fix] or [feat]
python guardian/rollback.py --show --pattern "fix\|feat"

# Find auto-sync commits
python guardian/rollback.py --show --pattern "auto-sync"
```

## Safety Features

Both scripts include multiple safety mechanisms:

### install.py Safety

- Detects existing hooks and prompts before overwriting
- Backs up non-Doc Guardian hooks with `.backup` suffix
- Validates guardian directory exists before installing
- Makes hooks exit 0 even on healing failures (post-commit)

### rollback.py Safety

- Shows commit details before reverting
- Lists affected files
- Prompts for confirmation (unless `--no-edit`)
- Creates backups when restoring files
- Uses `git revert` (not destructive operations)

## Error Handling

Both scripts handle common errors gracefully:

- Not in a git repository → Clear error message
- Guardian directory not found → Lists search locations
- Backup file not found → Suggests alternative
- Git commands fail → Shows git error output

## Integration with heal.py

These utilities complement `heal.py`:

```
heal.py --check        # Detect issues
  ↓
install.py             # Set up automation
  ↓
[Hooks run automatically]
  ↓
rollback.py            # Undo if needed
```

## Examples

### Typical Workflow

```bash
# 1. Install hooks
python guardian/install.py

# 2. Make commits (hooks run automatically)
git commit -m "feat: add new feature"
# → post-commit hook runs healing

# 3. Check what was healed
python guardian/rollback.py --show

# 4. Undo if needed
python guardian/rollback.py --last

# 5. Uninstall hooks later
python guardian/install.py --uninstall
```

### CI/CD Integration

```bash
# In CI pipeline
python guardian/install.py --hook pre-push
git push  # Blocks if docs have issues

# Or run check directly
python guardian/heal.py --check --verbose
```

### Selective Hook Installation

```bash
# Only install post-commit (auto-healing)
python guardian/install.py --hook post-commit

# Only install pre-push (validation)
python guardian/install.py --hook pre-push
```

## File Locations

Both scripts auto-detect locations:

- **Git root**: Found via `git rev-parse --show-toplevel`
- **Guardian dir**: Searches common locations (doc-guardian/guardian, guardian, .guardian)
- **Hooks dir**: `.git/hooks/` in git root
- **Backups**: Adjacent to original file with `.backup` suffix

## Exit Codes

Scripts follow Unix conventions:

- `0`: Success
- `1`: Failure (with error message)

Useful for scripting:

```bash
python guardian/install.py && echo "Hooks installed" || echo "Failed"
python guardian/rollback.py --last || echo "Rollback failed"
```

## Development Notes

### Adding New Hooks

Edit the `HOOKS` dictionary in `install.py`:

```python
HOOKS = {
    'your-hook-name': '''#!/bin/bash
# Your hook script
python3 "$GUARDIAN_DIR/heal.py" --your-flags
''',
}
```

### Customizing Search Patterns

Modify the `--pattern` default in `rollback.py`:

```python
parser.add_argument('--pattern', default='docs',
                    help="Git grep pattern for healing commits")
```

### Hook Detection

Hooks are identified as "Doc Guardian" if they contain the string "Doc Guardian" in the script. This allows:

- Installing alongside other hooks (with manual merge)
- Safe uninstallation (only removes our hooks)
- Backup preservation

## Troubleshooting

### "Not in a git repository"

Run from anywhere inside a git repository:

```bash
cd /path/to/your/repo
python /path/to/doc-guardian/guardian/install.py
```

### "Could not find guardian directory"

Ensure `heal.py` exists in one of these locations:

- `doc-guardian/guardian/heal.py`
- `guardian/heal.py`
- `.guardian/heal.py`

### "Hook already exists"

Use `--force` to overwrite (creates backup):

```bash
python guardian/install.py --force
```

Or manually merge with existing hook.

### Rollback finds no commits

Healing commits must include `[docs]` prefix:

```bash
git commit -m "[docs] fix broken links"  # Will be found
git commit -m "fix links"                # Won't be found
```

Customize pattern:

```bash
python guardian/rollback.py --show --pattern "fix"
```

## Future Enhancements

Potential improvements:

1. **Merge mode**: Intelligently merge with existing hooks
2. **Dry-run**: Preview hook actions without installing
3. **Selective rollback**: Revert only specific files from a commit
4. **Backup browsing**: List all available backups with timestamps
5. **Hook chaining**: Call original hook + Doc Guardian hook
