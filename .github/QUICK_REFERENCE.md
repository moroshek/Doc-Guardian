# GitHub Actions Quick Reference

Quick reference for Doc Guardian CI/CD workflows.

---

## 🚀 Workflows at a Glance

| Workflow | Trigger | Duration | Purpose |
|----------|---------|----------|---------|
| **Tests** | Push/PR | ~10 min | Run tests on 15 OS/Python combos |
| **Lint** | Push/PR | ~5 min | Check code quality |
| **Release** | Tag push | ~8 min | Build + publish to GitHub/PyPI |

---

## 📋 Workflow Files

```
.github/workflows/
├── test.yml    - Testing suite (unit, integration, coverage)
├── lint.yml    - Code quality (ruff, black, mypy, markdown, security)
└── release.yml - Automated releases (GitHub + PyPI)
```

---

## ✅ What Runs When

### Every Commit (Push/PR to main or develop)

```
Test Workflow:
  ✓ 15 OS/Python combinations
  ✓ Optional dependencies (yaml, jinja, toml, all)
  ✓ Parallel test execution
  ✓ Integration tests
  ✓ Coverage upload (ubuntu + 3.11 only)

Lint Workflow:
  ✓ ruff (Python linting)
  ✓ black (code formatting)
  ✓ mypy (type checking) - non-blocking
  ✓ markdownlint (doc quality) - non-blocking
  ✓ pyproject.toml validation
  ✓ Security checks (bandit + safety) - non-blocking
```

### Tag Push (v*)

```
Release Workflow:
  ✓ Build source distribution + wheel
  ✓ Extract changelog
  ✓ Create GitHub release
  ✓ Publish to PyPI (production tags)
  ✓ Publish to Test PyPI (prerelease tags)
  ✓ Verify installation
```

---

## 🏷️ Badge Status

Add to README.md:

```markdown
[![Tests](https://github.com/anthropics/doc-guardian/workflows/Tests/badge.svg)](https://github.com/anthropics/doc-guardian/actions/workflows/test.yml)
[![Lint](https://github.com/anthropics/doc-guardian/workflows/Lint/badge.svg)](https://github.com/anthropics/doc-guardian/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/anthropics/doc-guardian/branch/main/graph/badge.svg)](https://codecov.io/gh/anthropics/doc-guardian)
```

---

## 🔐 Required Secrets

| Secret | Required? | Purpose | Where to Get |
|--------|-----------|---------|--------------|
| `CODECOV_TOKEN` | Optional | Coverage reports | https://codecov.io |
| `PYPI_API_TOKEN` | For releases | Publish to PyPI | https://pypi.org/manage/account/token/ |
| `TEST_PYPI_API_TOKEN` | Optional | Prerelease testing | https://test.pypi.org/manage/account/token/ |

**Add secrets**: Repo → Settings → Secrets and variables → Actions → New repository secret

---

## 📦 Release Process

### Standard Release (PyPI)

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

### Prerelease (Test PyPI)

```bash
# 1. Update version with suffix
vim guardian/__init__.py  # __version__ = "0.2.0-beta.1"

# 2. Create + push tag
git tag v0.2.0-beta.1
git push origin v0.2.0-beta.1

# ✅ Publishes to Test PyPI only
```

---

## 🐛 Debugging Failed Workflows

### Tests Failed

1. **Check Actions tab** → Find failed job
2. **View logs** → Expand failed step
3. **Common issues**:
   - Import errors: Check dependencies
   - Test failures: Run locally first
   - OS-specific: May only fail on Windows/macOS

### Lint Failed

1. **Run locally**:
   ```bash
   ruff check guardian/ tests/
   ruff format --check guardian/ tests/
   black --check guardian/ tests/
   ```
2. **Auto-fix**:
   ```bash
   ruff format guardian/ tests/
   black guardian/ tests/
   ```

### Release Failed

1. **Check tag format**: Must be `v*` (e.g., v0.2.0)
2. **Check secrets**: PYPI_API_TOKEN must be set
3. **Check version**: Must not already exist on PyPI

---

## 🔧 Local Testing

Before pushing, run these to catch issues:

```bash
# Quick check
pytest tests/ -v
ruff check guardian/ tests/

# Full check (CI equivalent)
pytest --cov=guardian --cov-report=term -v
ruff check guardian/ tests/ examples/
ruff format --check guardian/ tests/ examples/
black --check guardian/ tests/ examples/
mypy guardian/ --ignore-missing-imports
```

---

## ⚙️ Customization

### Skip Workflow

Add to commit message:
```
[skip ci]
```

### Run Specific Job

Not supported natively. Use:
```yaml
if: github.event_name == 'workflow_dispatch'
```

Then trigger manually from Actions tab.

### Change Python Versions

Edit `test.yml`:
```yaml
matrix:
  python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
```

---

## 📊 Workflow Status

Check status:
- **Actions tab**: https://github.com/anthropics/doc-guardian/actions
- **README badges**: See build status at a glance
- **Email**: GitHub sends failure notifications (configure in settings)

---

## 🆘 Common Commands

```bash
# Check workflow syntax locally
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"

# Validate all workflows
for f in .github/workflows/*.yml; do
  python3 -c "import yaml; yaml.safe_load(open('$f'))" && echo "✓ $f"
done

# List workflow runs
gh run list --limit 10

# View workflow logs
gh run view <run-id> --log

# Re-run failed workflow
gh run rerun <run-id>
```

---

## 📚 Full Documentation

- **Complete guide**: `.github/CI_CD.md`
- **Comparison**: `.github/WORKFLOW_COMPARISON.md`
- **Summary**: `CI_CD_SUMMARY.md`

---

**Quick Links**:
- [Actions Tab](https://github.com/anthropics/doc-guardian/actions)
- [Workflow Files](https://github.com/anthropics/doc-guardian/tree/main/.github/workflows)
- [Settings → Secrets](https://github.com/anthropics/doc-guardian/settings/secrets/actions)

---

**Last Updated**: 2026-01-11
