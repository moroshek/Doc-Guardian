# Compatibility

## Python Versions

**Minimum**: Python 3.8+
**Tested on**: 3.8, 3.9, 3.10, 3.11, 3.12
**Recommended**: 3.10 or newer

### Version Requirements

Doc Guardian requires Python 3.8+ due to:
- **Walrus operator (`:=`)** - Used in sync_canonical.py for pattern matching
- **typing module** - Standard typing annotations (Dict, List, Optional, etc.)
- **dataclasses** - Core data structures (Change, HealingReport, etc.)

### Version-Specific Notes

#### Python 3.8
- Minimum supported version
- All features work correctly
- Uses `typing.Dict`, `typing.List` instead of built-in generics

#### Python 3.9+
- Built-in generic types (`list[str]`, `dict[str, Any]`) not yet used
- Could be adopted in future versions
- String methods `removeprefix()`/`removesuffix()` not currently used

#### Python 3.10+
- Pattern matching (`match`/`case`) not used
- Union operator (`X | Y`) not used
- Maintains compatibility with 3.8

#### Python 3.11+
- Built-in TOML support (`tomllib`) used when available
- Falls back to optional `toml` package on older versions

#### Python 3.12+
- Fully compatible
- No 3.12-specific features required

## Operating Systems

### Linux
**Status**: ✅ Fully supported

- Primary development platform
- All features tested and working
- Native path handling
- Git integration fully functional
- ANSI color codes supported in all terminals

### macOS
**Status**: ✅ Fully supported

- All features work identically to Linux
- Native path handling with POSIX paths
- Git integration fully functional
- ANSI color codes supported in Terminal.app and iTerm2

### Windows
**Status**: ⚠️ Supported with limitations

#### What Works
- Core healing functionality
- File operations (read, write, atomic updates)
- Git integration (via Git Bash or WSL)
- Path validation and security features

#### Known Limitations
1. **Path Separators**: Use forward slashes (`/`) in config files, not backslashes (`\`)
2. **Git Hooks**: Require Git Bash or WSL for execution
3. **Colors**: ANSI codes may not display in cmd.exe (use Windows Terminal instead)
4. **Line Endings**: Git should be configured with `core.autocrlf=true`

#### Recommended Setup for Windows
```bash
# Use Git Bash (recommended)
git-bash.exe

# Or use WSL2 (Ubuntu)
wsl --install

# Configure Git line endings
git config --global core.autocrlf true

# Use Windows Terminal for proper ANSI support
# Download from Microsoft Store
```

#### Windows-Specific Configuration
```toml
# In .docguardian.toml, use forward slashes
project_root = "C:/Users/yourname/project"
doc_root = "C:/Users/yourname/project/docs"

# NOT backslashes (will cause validation errors)
# project_root = "C:\\Users\\yourname\\project"  # ❌ Don't do this
```

## Dependencies

### Runtime Dependencies
**Zero runtime dependencies** - Uses only Python standard library:
- `pathlib` - Path manipulation
- `re` - Regular expressions
- `json` - Configuration parsing
- `subprocess` - Git operations
- `dataclasses` - Data structures
- `typing` - Type annotations
- `argparse` - CLI interface
- `logging` - Event logging
- `hashlib` - File similarity (simhash)
- `difflib` - String similarity
- `collections` - Data structures
- `concurrent.futures` - Parallel processing
- `tempfile` - Atomic file operations
- `signal` - Graceful shutdown
- `contextlib` - Resource management

### Optional Dependencies

#### YAML Support
```bash
pip install doc-guardian[yaml]
```
Adds support for YAML config files (`.docguardian.yaml`)

#### Jinja2 Templates
```bash
pip install doc-guardian[jinja]
```
Future feature for template-based content generation

#### TOML Support (Python < 3.11)
```bash
pip install doc-guardian[toml]
```
TOML parsing on Python 3.10 and older (3.11+ has built-in support)

#### All Optional Dependencies
```bash
pip install doc-guardian[all]
```

#### Development Dependencies
```bash
pip install doc-guardian[dev]
```
Includes pytest, mypy, ruff, coverage tools

## File System

### Encoding
- **UTF-8** - All files must be UTF-8 encoded
- Non-UTF-8 files will trigger validation errors
- BOM (Byte Order Mark) is handled correctly

### Line Endings
- **LF** (`\n`) - Preferred on Linux/macOS
- **CRLF** (`\r\n`) - Accepted on Windows
- Git should normalize line endings (`core.autocrlf`)

### File Size Limits
- **Default**: 10 MB per file (configurable)
- Prevents memory exhaustion attacks
- See `security.max_file_size_bytes` in config

### Path Handling
- **Absolute paths** - Validated against project root
- **Relative paths** - Resolved from current directory
- **Symlinks** - Validated to stay within project root
- **Directory traversal** - Blocked by path validator

## Performance

### System Requirements
- **CPU**: Any modern CPU (multi-core recommended for parallel healing)
- **Memory**: ~50 MB base + ~1 MB per 100 markdown files
- **Disk**: Minimal (logs are rotated, caches are bounded)

### Scalability
Tested on repositories with:
- ✅ Up to 1,000 markdown files
- ✅ Up to 10,000 total files in repository
- ✅ Files up to 10 MB each
- ✅ Repositories up to 1 GB total size

For larger repositories:
- Increase `max_file_size_bytes` if needed
- Use `--workers` to control parallelism
- Consider running healers selectively (not all at once)

## Git Integration

### Git Versions
- **Minimum**: Git 2.0+
- **Recommended**: Git 2.30+
- **Tested**: Git 2.25 through 2.43

### Git Hooks
- Requires executable hook files (chmod +x)
- Must be in `.git/hooks/` directory
- Not supported in shallow clones (`--depth=1`)

### Git Worktrees
- ⚠️ Not fully tested with git worktrees
- Each worktree needs separate hook installation

## Known Issues

### Platform-Specific

#### Windows
- ❌ Symlinks require admin privileges or Developer Mode
- ⚠️ Paths with non-ASCII characters may need special handling
- ⚠️ Git Bash required for hook execution

#### macOS
- ✅ No known issues

#### Linux
- ✅ No known issues

### Python-Specific

#### Python 3.8
- ⚠️ Type hints may show as strings in error messages
- ⚠️ `typing.get_type_hints()` may fail without `from __future__ import annotations`

#### Python 3.12
- ⚠️ Some deprecation warnings from stdlib (harmless)

### Git-Specific
- ⚠️ Pre-commit hooks slow down commits (by design)
- ⚠️ Hooks don't run on `git commit --no-verify` (by design)

## Testing Your Installation

### Basic Test
```bash
# Test imports
python3 -c "from guardian.heal import main; print('✓ Imports work')"

# Test CLI
doc-guardian --version

# Run self-test
doc-guardian heal --dry-run
```

### Platform-Specific Tests

#### Windows
```bash
# In Git Bash
python --version  # Should be 3.8+
git --version     # Should be 2.0+
doc-guardian heal --help  # Should show usage
```

#### Linux/macOS
```bash
python3 --version  # Should be 3.8+
git --version      # Should be 2.0+
doc-guardian heal --help  # Should show usage
```

### Test Git Integration
```bash
cd /path/to/your/repo
guardian-install  # Install hooks
echo "test" >> README.md
git add README.md
git commit -m "test"  # Hook should run
```

## Reporting Issues

If you encounter compatibility issues:

1. **Check versions**:
   ```bash
   python3 --version
   git --version
   uname -a  # Linux/macOS
   ver       # Windows
   ```

2. **Collect debug info**:
   ```bash
   doc-guardian heal --verbose --dry-run 2>&1 | tee debug.log
   ```

3. **Report issue** with:
   - Python version
   - OS and version
   - Git version
   - Full error message
   - `debug.log` output

## Future Compatibility

### Upcoming Python Features
- **Python 3.13+**: Will adopt new typing features when released
- **Built-in generics**: May migrate from `typing.List` to `list` in future
- **Pattern matching**: May adopt `match`/`case` if valuable

### Deprecation Timeline
- **Python 3.8**: Already EOL (October 2024). We continue to support it for legacy systems.
- **Python 3.9**: Support until October 2025 (EOL)
- **Minimum version**: May increase to 3.10+ in late 2025

Future versions will maintain backward compatibility where possible.
