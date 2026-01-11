# GitHub Configuration

This directory contains GitHub-specific configuration files for Doc Guardian.

---

## 📂 Directory Structure

```
.github/
├── workflows/           # GitHub Actions workflows
│   ├── test.yml        # Testing suite (unit, integration, coverage)
│   ├── lint.yml        # Code quality (ruff, black, mypy, markdown, security)
│   ├── release.yml     # Automated releases (GitHub + PyPI)
│   └── ci.yml          # Legacy CI workflow (can be removed)
├── CI_CD.md            # Complete CI/CD documentation
├── WORKFLOW_COMPARISON.md  # Comparison of old vs new workflows
├── QUICK_REFERENCE.md  # Quick reference card for developers
└── README.md           # This file
```

---

## 🚀 Workflows

### test.yml - Testing & Coverage

**Purpose**: Comprehensive testing across Python versions and operating systems.

**Features**:
- Matrix testing: Python 3.8-3.12 on ubuntu/macos/windows
- Optional dependencies: yaml, jinja, toml, all
- Parallel execution: pytest-xdist
- Integration tests: Real config testing
- Coverage: Upload to Codecov + badge generation

**Triggers**: Push/PR to main or develop branches

**Duration**: ~10 minutes

---

### lint.yml - Code Quality

**Purpose**: Enforce code quality standards and best practices.

**Features**:
- ruff: Python linting
- black: Code formatting
- mypy: Type checking (non-blocking)
- markdownlint: Documentation quality (non-blocking)
- pyproject validation: Metadata correctness
- Security: bandit + safety (non-blocking)

**Triggers**: Push/PR to main or develop branches

**Duration**: ~5 minutes

---

### release.yml - Automated Releases

**Purpose**: Automated release creation and distribution.

**Features**:
- Build: Source distribution + wheel
- Changelog: Auto-extract from CHANGELOG.md
- GitHub Release: Create with artifacts
- PyPI: Publish to production PyPI
- Test PyPI: Publish prereleases
- Verification: Post-release smoke tests

**Triggers**: Push to tags matching `v*` (e.g., v0.2.0)

**Duration**: ~8 minutes

---

## 📚 Documentation

| File | Purpose | Audience |
|------|---------|----------|
| `CI_CD.md` | Complete CI/CD guide with troubleshooting | All developers |
| `WORKFLOW_COMPARISON.md` | Comparison with existing ci.yml | Maintainers |
| `QUICK_REFERENCE.md` | Quick reference for common tasks | Daily users |
| `README.md` | This file - overview and navigation | New contributors |

---

## 🔐 Required Secrets

To enable full CI/CD functionality, add these secrets to your repository:

| Secret | Required? | Purpose |
|--------|-----------|---------|
| `CODECOV_TOKEN` | Optional | Coverage reporting |
| `PYPI_API_TOKEN` | For releases | Publish to PyPI |
| `TEST_PYPI_API_TOKEN` | Optional | Prerelease testing |

**How to add**: Repo Settings → Secrets and variables → Actions → New repository secret

---

## 🎯 Quick Start

### For Contributors (Testing)

Before pushing:
```bash
# Run tests
pytest tests/ -v

# Check linting
ruff check guardian/ tests/
black --check guardian/ tests/
```

### For Maintainers (Releases)

```bash
# 1. Update version
vim guardian/__init__.py  # __version__ = "0.2.0"
vim pyproject.toml        # version = "0.2.0"

# 2. Update changelog
vim CHANGELOG.md

# 3. Commit + tag
git add .
git commit -m "Release v0.2.0"
git push origin main
git tag v0.2.0
git push origin v0.2.0

# ✅ GitHub Actions handles the rest
```

---

## 🏷️ Badges

Current badges in README.md:

```markdown
[![Tests](https://github.com/anthropics/doc-guardian/workflows/Tests/badge.svg)](https://github.com/anthropics/doc-guardian/actions/workflows/test.yml)
[![Lint](https://github.com/anthropics/doc-guardian/workflows/Lint/badge.svg)](https://github.com/anthropics/doc-guardian/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/anthropics/doc-guardian/branch/main/graph/badge.svg)](https://codecov.io/gh/anthropics/doc-guardian)
```

---

## 🔧 Customization

### Add Python Version

Edit `test.yml`:
```yaml
matrix:
  python-version: ['3.8', '3.9', '3.10', '3.11', '3.12', '3.13']  # Add 3.13
```

### Disable Non-Critical Checks

Edit `lint.yml`:
```yaml
mypy:
  if: false  # Disable type checking
```

### Change Release Trigger

Edit `release.yml`:
```yaml
on:
  push:
    tags:
      - 'release-*'  # Change tag pattern
```

---

## 📊 Monitoring

### View Workflow Status

- **Actions tab**: https://github.com/anthropics/doc-guardian/actions
- **README badges**: Build status at a glance
- **Email notifications**: Configure in GitHub settings

### Debugging Failed Runs

1. Go to Actions tab
2. Click failed workflow run
3. Click failed job
4. Expand failed step to view logs

---

## 🆘 Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Tests fail on Windows | Path separator issues | Use `pathlib.Path` |
| Coverage upload fails | Missing token | Add `CODECOV_TOKEN` secret |
| Release fails | Version exists | Increment version number |
| Lint fails | Code not formatted | Run `ruff format` + `black` |

See `CI_CD.md` for detailed troubleshooting guide.

---

## 📝 Migration from ci.yml

The existing `ci.yml` workflow can be:

1. **Removed** - New workflows have feature parity
2. **Renamed** to `ci-legacy.yml` for reference
3. **Disabled** - Change trigger to `workflow_dispatch` only

See `WORKFLOW_COMPARISON.md` for detailed comparison.

---

## 🔄 Workflow Dependency Graph

```
On Push/PR:
  lint.yml ────┐
  test.yml ────┼──► Success? ──► Merge allowed
                │
Integration ───┘

On Tag Push (v*):
  test.yml + lint.yml must have passed
       ↓
  release.yml ──► Build ──► GitHub Release ──► PyPI
```

---

## 📅 Maintenance Schedule

- **Weekly**: Review failed runs, update dependencies
- **Monthly**: Check for GitHub Actions updates
- **Quarterly**: Review and update Python version matrix
- **Yearly**: Audit and update security tools (bandit, safety)

---

## 🤝 Contributing

When modifying workflows:

1. Test changes on a fork first
2. Use `act` for local GitHub Actions testing
3. Update relevant documentation
4. Test on feature branch before main
5. Keep this README updated

---

## 📖 Learn More

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Doc Guardian Main README](../README.md)
- [Contributing Guide](../CONTRIBUTING.md)

---

**Quick Links**:
- [View Workflows](https://github.com/anthropics/doc-guardian/actions)
- [Manage Secrets](https://github.com/anthropics/doc-guardian/settings/secrets/actions)
- [Edit Workflows](https://github.com/anthropics/doc-guardian/tree/main/.github/workflows)

---

**Last Updated**: 2026-01-11
