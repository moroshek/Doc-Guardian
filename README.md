# Doc Guardian

> Your documentation fixes itself while you sleep

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---

## Executive Summary

**Doc Guardian automatically maintains your documentation** so your team doesn't have to.

When you refactor code, Doc Guardian fixes broken links. When APIs change, it updates docs automatically. When content gets stale, it flags it. **No manual work, no broken promises to "update the docs later."**

**ROI**: Teams spend **2-4 hours/week** manually fixing docs. Doc Guardian reduces this to **15 minutes/week**.

**How it works**: 7 autonomous "healers" scan your docs, detect issues, and auto-fix them with 90%+ confidence. Every change is reversible via git. Zero API calls, zero external dependencies.

**Who uses it**: Engineering teams tired of broken docs, technical writers managing large doc sets, DevOps teams integrating doc checks into CI/CD.

---

## The Problem: Documentation Decay

Every team faces these issues:

| Problem | Manual Fix | Time Cost |
|---------|-----------|-----------|
| **Broken links** after code refactor | Search files, update paths manually | 30-45 min |
| **Stale timestamps** (`Last updated: 2023-01-15`) | Remember to update after every commit | 10-15 min |
| **Duplicate content** across files | Find duplicates, consolidate, maintain | 1-2 hours |
| **Out-of-sync API docs** after schema changes | Manually sync JSON/YAML → markdown | 45-60 min |
| **Dead links** to moved/deleted files | Find broken refs, update or remove | 20-30 min |

**Total**: 2-4 hours/week per team member on "doc maintenance."

**The Real Cost**: Developers avoid updating docs because it's tedious. Docs fall out of sync. New team members get confused. Support tickets increase.

---

## The Solution: Autonomous Healers

Doc Guardian uses **7 specialized "healers"** that automatically fix specific documentation problems:

### 1. Fix Broken Links 🔗
**What it does**: Finds broken internal links and auto-fixes them by fuzzy-matching file names.

**Why this helps**: After refactoring `api/auth.md` → `api/authentication.md`, all 23 links to the old path break. Manually finding and fixing them takes 30+ minutes. **Doc Guardian fixes them in 3 seconds with 95% accuracy.**

**Example**:
- Broken: `[See authentication](api/auth.md)` ❌
- Fixed: `[See authentication](api/authentication.md)` ✅

---

### 2. Detect Staleness ⏰
**What it does**: Flags docs older than N days (configurable). Updates "Last modified" timestamps. Detects deprecated commands (e.g., `npm install -g` → `npm install`).

**Why this helps**: Stale docs mislead users. Manually tracking which docs need updating is impossible at scale. **Doc Guardian auto-flags anything untouched in 30+ days and updates timestamps on every commit.**

**Example**:
- Before: `Last updated: 2023-01-15` ❌
- After: `Last updated: 2026-01-11` ✅

---

### 3. Resolve Duplicates 📋
**What it does**: Finds duplicate content blocks across files and consolidates them.

**Why this helps**: Teams copy-paste setup instructions into 5 different docs. When the setup changes, 4 copies get outdated. **Doc Guardian finds duplicates with 85%+ confidence and suggests consolidation.**

**Example**:
- Finds: "Installation" section duplicated in `README.md`, `QUICKSTART.md`, `SETUP.md`
- Suggests: Keep in `README.md`, link from others

---

### 4. Balance References 🔄
**What it does**: Ensures bidirectional links between related docs (if A links to B, B should link back to A).

**Why this helps**: Users click into a deep doc and can't find their way back. **Doc Guardian auto-adds "See also" sections linking related docs.**

**Example**:
- `authentication.md` links to `api-keys.md` ✅
- `api-keys.md` doesn't link back ❌
- Doc Guardian adds: `**See also**: [Authentication Guide](authentication.md)` ✅

---

### 5. Sync Canonical Sources 🔄
**What it does**: Keeps docs in sync with source-of-truth files (JSON schemas, YAML configs, TOML files).

**Why this helps**: API docs drift from OpenAPI specs. Config docs don't match actual YAML files. **Doc Guardian auto-generates markdown from source files on every change.**

**Example**:
- `openapi.yaml` adds new endpoint `/v2/users`
- Doc Guardian auto-adds to `api-reference.md`
- Runs on every commit via git hook

---

### 6. Manage Collapsed Sections 📦
**What it does**: Auto-collapses long sections (>50 lines) using `<details>` tags for better readability.

**Why this helps**: Long docs overwhelm readers. Manually adding collapse tags is tedious. **Doc Guardian auto-collapses long sections while keeping important content visible.**

**Example**:
```markdown
<details>
<summary>Full API Reference (click to expand)</summary>

[500 lines of API docs...]
</details>
```

---

### 7. Enforce Progressive Disclosure 📚
**What it does**: Maintains doc architecture layers (Overview → Guide → Reference) with max line limits per layer.

**Why this helps**: Docs that try to explain everything at once confuse users. **Doc Guardian enforces layered disclosure** (quick start ≤50 lines, guides ≤500 lines, reference unlimited).

**Example**:
- `README.md` exceeds 50 lines → Flags for splitting
- Suggests: Move details to `docs/quickstart.md`

---

## Quick Start

```bash
# 1. Clone into your project
git clone https://github.com/moroshek/Doc-Guardian .doc-guardian
cd .doc-guardian

# 2. Configure (2 minutes)
cp config.toml.template config.toml
# Edit: Set doc_root to your docs directory

# 3. Preview changes (dry run)
python guardian/heal.py --config config.toml --check

# 4. Apply fixes
python guardian/heal.py --config config.toml --heal
```

**Minimal config** (5 lines):
```toml
[project]
doc_root = "../docs/"

[healers]
fix_broken_links = { enabled = true }
detect_staleness = { enabled = true }
```

---

## How It Works: See It In Action

### Check Mode (Dry Run)
```bash
$ python guardian/heal.py --config config.toml --check

📋 Documentation Healing Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mode: check
Execution Time: 2.34s

Summary
- Healers Run: 7
- Total Issues Found: 26

Healer Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Fix Broken Links
   Issues Found: 15
   Confidence: 92-98%

⏰ Detect Staleness
   Issues Found: 8
   Confidence: 100%

📋 Resolve Duplicates
   Issues Found: 3
   Confidence: 85-90%
```

### Heal Mode (Apply Fixes)
```bash
$ python guardian/heal.py --config config.toml --heal

📋 Documentation Healing Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mode: heal
Execution Time: 3.12s

Summary
- Total Issues Found: 26
- Total Issues Fixed: 23
- Success Rate: 88.5%

✅ Report saved to reports/healing_report.md
✅ Changes committed: [docs] Auto-fix 23 documentation issues
```

---

## Confidence-Based Healing

Doc Guardian **only auto-fixes changes it's confident about** (default: 90%+).

### How Confidence Is Calculated

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| **Pattern Match** | 40% | How well the fix matches known patterns (e.g., file exists at fuzzy-matched path) |
| **Change Size** | 30% | Smaller changes = higher confidence (changing 1 link > rewriting paragraph) |
| **Risk Level** | 20% | Content changes (low risk) vs structure changes (higher risk) |
| **History** | 10% | Past success rate of similar fixes |

### What Happens at Different Confidence Levels

| Confidence | Action | Example |
|------------|--------|---------|
| **≥90%** | Auto-commit | Broken link to moved file |
| **≥80%** | Auto-stage for review | Duplicate content detected |
| **≥50%** | Report only | Potential stale doc (needs human judgment) |
| **<50%** | Skip (silent) | Low-quality match, ignore |

### Override Thresholds

```bash
# Ultra-conservative (only 95%+ confidence)
python guardian/heal.py --heal --min-confidence 0.95

# More aggressive (80%+ confidence)
python guardian/heal.py --heal --min-confidence 0.80
```

---

## Git Integration & Safety

Every change is **fully reversible** via git.

### Auto-Commit
```toml
[git]
auto_commit = true
commit_prefix = "[docs]"
```

Doc Guardian creates detailed commit messages:
```bash
[docs] Fix 15 broken links in api/ directory
[docs] Update timestamps in 8 stale documents
```

### Rollback
```bash
# Show recent commits
python guardian/rollback.py --show

# Rollback last healing
python guardian/rollback.py --last

# Interactive rollback
python guardian/rollback.py
```

### Git Hooks (Auto-Heal on Commit)
```bash
# Install hooks
python guardian/install.py --config config.toml

# Every commit now auto-runs healers
git commit -m "Add new feature"
# → Doc Guardian runs, fixes any broken links
```

---

## CI/CD Integration

**Block PRs with doc issues:**
```yaml
# .github/workflows/docs.yml
- name: Check documentation health
  run: python .doc-guardian/guardian/heal.py --check --strict
```

**Auto-heal in CI:**
```yaml
- name: Auto-fix documentation
  run: |
    python .doc-guardian/guardian/heal.py --heal --min-confidence 0.95
    git add docs/ && git commit -m "[docs] Auto-heal" || true
```

---

## Configuration Examples

### Python API Project
```toml
[project]
doc_root = "docs/"
excluded_dirs = [".git", "venv", "__pycache__"]

[healers.fix_broken_links]
enabled = true
fuzzy_threshold = 0.70  # Looser for Python naming

[healers.detect_staleness]
staleness_threshold_days = 30
deprecated_patterns = ['python2\s+', 'sudo\s+pip']

[healers.sync_canonical]
enabled = true
source_files = ["openapi.yaml"]  # Sync from OpenAPI spec
```

### React Component Library
```toml
[project]
doc_root = "docs/"
excluded_dirs = ["node_modules", "dist", "storybook-static"]

[healers.detect_staleness]
staleness_threshold_days = 60  # Components change less frequently

[healers.sync_canonical]
source_files = ["package.json"]  # Sync version from package.json
```

### Markdown Wiki
```toml
[project]
doc_root = "."  # Root is the wiki

[healers.balance_references]
enabled = true
backlink_format = "**See also**: [{title}]({path})"

[healers.resolve_duplicates]
similarity_threshold = 0.85
hierarchy_rules = ["index.md", "Home.md", "guides/", "reference/"]
```

See [CUSTOMIZATION.md](CUSTOMIZATION.md) for 7 complete project configs.

---

## Advanced Usage

### Run Specific Healers
```bash
# Only fix broken links
python guardian/heal.py --heal --only fix_broken_links

# Skip staleness detection
python guardian/heal.py --heal --skip detect_staleness

# Run multiple specific healers
python guardian/heal.py --heal --only fix_broken_links,detect_staleness
```

### Parallel Execution (Faster)
```bash
# Run independent healers in parallel
python guardian/heal.py --heal --parallel --max-workers 4
```

### Dry Run Preview
```bash
# See what would change without applying
python guardian/heal.py --heal --dry-run --verbose
```

### List Available Healers
```bash
$ python guardian/heal.py --list

Healer execution order:
  1. sync_canonical       ✅ enabled
  2. fix_broken_links     ✅ enabled
  3. detect_staleness     ✅ enabled
  4. resolve_duplicates   ✅ enabled
  5. balance_references   ❌ disabled
  6. manage_collapsed     ❌ disabled
  7. enforce_disclosure   ❌ disabled
```

---

## Writing Custom Healers

Extend Doc Guardian with project-specific healers. The base class handles confidence scoring, git integration, and reporting—you just implement the detection logic.

**Example** (complete healer in ~20 lines):
```python
# guardian/healers/fix_typos.py
from guardian.core.base import HealingSystem

class FixTyposHealer(HealingSystem):
    def check(self):
        changes = []
        for doc in self.doc_root.rglob('*.md'):
            for typo, fix in self.config['rules'].items():
                if typo in doc.read_text():
                    changes.append(self.create_change(
                        file=doc, old=typo, new=fix,
                        confidence=0.95, reason=f"Fix typo: {typo} → {fix}"
                    ))
        return self.create_report(changes)
```

**See**: [CUSTOM_HEALER_QUICKSTART.md](CUSTOM_HEALER_QUICKSTART.md) for complete guide with config examples.

---

## Real-World Examples

See **4 complete working examples** in [`integration-tests/`](integration-tests/):

| Example | Use Case | Key Features |
|---------|----------|--------------|
| **[python-api-project](integration-tests/python-api-project/)** | REST API docs | Sync from OpenAPI schema, fix broken links, detect stale endpoints |
| **[react-component-lib](integration-tests/react-component-lib/)** | Component library | Sync version from package.json, manage collapsed examples |
| **[rust-cli-tool](integration-tests/rust-cli-tool/)** | CLI tool docs | Sync from Cargo.toml, enforce progressive disclosure |
| **[markdown-wiki](integration-tests/markdown-wiki/)** | Knowledge base | Balance references, resolve duplicates, detect staleness |

Each includes:
- Complete `config.toml`
- Before/after examples
- Verification script
- Expected results

---

## Documentation

| Document | Description |
|----------|-------------|
| **[CUSTOMIZATION.md](CUSTOMIZATION.md)** | 7 project-specific configs (Python, React, Rust, Wiki, etc.) |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | How Doc Guardian works internally |
| **[CONFIG_GUIDE.md](CONFIG_GUIDE.md)** | Complete configuration reference |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | How to contribute |
| **[docs/CUSTOM_HEALERS.md](docs/CUSTOM_HEALERS.md)** | Complete custom healer guide |
| **[docs/guides/](docs/guides/)** | Confidence model, git integration, troubleshooting |
| **[docs/reference/](docs/reference/)** | API reference, CLI reference, config reference |

---

## Installation

**Prerequisites**: Python 3.8+, Git

```bash
# Clone into your project
cd your-project/
git clone https://github.com/moroshek/Doc-Guardian .doc-guardian

# Or use as Git submodule
git submodule add https://github.com/moroshek/Doc-Guardian .doc-guardian

# Configure
cd .doc-guardian
cp config.toml.template config.toml
# Edit config.toml with your doc_root
```

**Zero dependencies**. Uses Python stdlib only.

---

## Compatibility

| Platform | Status | Notes |
|----------|--------|-------|
| **Linux** | ✅ Fully supported | Primary development platform |
| **macOS** | ✅ Fully supported | Tested on Intel and Apple Silicon |
| **Windows** | ⚠️ Use Git Bash/WSL | Native cmd.exe not supported |

| Python Version | Status |
|----------------|--------|
| 3.8 | ✅ Tested |
| 3.9 | ✅ Tested |
| 3.10 | ✅ Tested |
| 3.11 | ✅ Recommended |
| 3.12 | ✅ Tested |

See [COMPATIBILITY.md](COMPATIBILITY.md) for detailed platform notes.

---

## Quick Reference

### Most Common Commands

```bash
# Check docs (dry run)
python guardian/heal.py --config config.toml --check

# Apply high-confidence fixes
python guardian/heal.py --config config.toml --heal

# Ultra-safe mode (95%+ confidence only)
python guardian/heal.py --config config.toml --heal --min-confidence 0.95

# List healers
python guardian/heal.py --config config.toml --list

# Install git hooks (auto-heal on commit)
python guardian/install.py --config config.toml

# Rollback last change
python guardian/rollback.py --last

# CI/CD (fail if issues found)
python guardian/heal.py --config config.toml --check --strict
```

### Configuration Cheat Sheet

```toml
# Minimal (5 lines)
[project]
doc_root = "docs/"
[healers]
fix_broken_links = { enabled = true }

# Recommended (15 lines)
[project]
doc_root = "docs/"
excluded_dirs = [".git", "node_modules", "venv"]

[confidence]
auto_commit_threshold = 0.90

[healers.fix_broken_links]
enabled = true
fuzzy_threshold = 0.80

[healers.detect_staleness]
enabled = true
staleness_threshold_days = 30

[git]
auto_commit = true
```

### Healer Flags

| Healer | Purpose | Enable If... |
|--------|---------|--------------|
| `fix_broken_links` | Fix moved/deleted file links | You refactor docs frequently |
| `detect_staleness` | Flag old docs, update timestamps | Docs go stale easily |
| `resolve_duplicates` | Find duplicate content | Content copied across files |
| `balance_references` | Add bidirectional links | Docs heavily cross-reference |
| `sync_canonical` | Sync from JSON/YAML/TOML | Docs generated from schemas |
| `manage_collapsed` | Collapse long sections | Docs have 500+ line files |
| `enforce_disclosure` | Enforce layer limits | Following progressive disclosure |

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

- **[Report bugs](https://github.com/moroshek/Doc-Guardian/issues)** - Something broken?
- **[Request features](https://github.com/moroshek/Doc-Guardian/issues)** - Got ideas?
- **[Submit PRs](https://github.com/moroshek/Doc-Guardian/pulls)** - Code improvements

---

## License

[MIT License](LICENSE) - Use freely in commercial and open-source projects.

---

## Project Status

**v0.1.0** - Production ready

All 7 healers stable and tested. 150+ test cases passing across Python 3.8-3.12.

**Roadmap**:
- PyPI package (`pip install doc-guardian`)
- GitHub Action
- VS Code extension

---

## Support

- **Documentation**: Full docs in [`docs/`](docs/)
- **Issues**: [GitHub Issues](https://github.com/moroshek/Doc-Guardian/issues)
- **Examples**: 4 complete examples in [`integration-tests/`](integration-tests/)

---

**Built for teams tired of broken docs.** 🛠️
