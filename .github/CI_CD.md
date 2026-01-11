# CI/CD Documentation

This document describes the GitHub Actions workflows for Doc Guardian.

## Workflows

### 1. Tests (`test.yml`)

**Triggers**: Push to main/develop, pull requests

**Purpose**: Comprehensive testing across Python versions and operating systems.

**Jobs**:

- **test**: Matrix testing
  - Python versions: 3.8, 3.9, 3.10, 3.11, 3.12
  - Operating systems: ubuntu-latest, macos-latest, windows-latest
  - Runs pytest with coverage
  - Uploads coverage to Codecov (ubuntu + Python 3.11 only)

- **test-optional-deps**: Test with optional dependencies
  - Tests each optional dependency group: yaml, jinja, toml, all

- **test-parallel**: Test with pytest-xdist
  - Runs tests in parallel using all CPU cores

- **test-summary**: Summary job
  - Checks results of all test jobs
  - Fails if any test job failed

**Coverage**:
- Coverage reports uploaded to Codecov
- Badge generated and uploaded as artifact
- Only for ubuntu-latest + Python 3.11 + main branch

**Caching**:
- pip dependencies cached via actions/setup-python

---

### 2. Lint (`lint.yml`)

**Triggers**: Push to main/develop, pull requests

**Purpose**: Code quality and style enforcement.

**Jobs**:

- **ruff**: Python linting
  - Checks: guardian/, tests/, examples/
  - Format check included

- **black**: Code formatting
  - Checks guardian/, tests/, examples/
  - Fails if code isn't formatted

- **mypy**: Type checking
  - Non-blocking (continue-on-error: true)
  - May have incomplete type hints

- **markdown-lint**: Markdown linting
  - Uses markdownlint-cli
  - Checks all *.md files
  - Config: .markdownlint.json
  - Non-blocking

- **pyproject-validate**: Validate pyproject.toml
  - Uses validate-pyproject
  - Ensures project metadata is valid

- **security**: Security checks
  - bandit: Security linter for Python
  - safety: Check dependency vulnerabilities
  - Non-blocking (reports only)

- **lint-summary**: Summary job
  - Fails on critical linting failures (ruff, black, pyproject)
  - Reports non-critical failures (mypy, markdown, security)

**Critical vs Non-Critical**:
- Critical (blocking): ruff, black, pyproject-validate
- Non-critical (reporting): mypy, markdown-lint, security

---

### 3. Release (`release.yml`)

**Triggers**: Push to tags matching `v*` (e.g., v0.1.0)

**Purpose**: Automated release creation and publishing.

**Jobs**:

- **build**: Build distribution packages
  - Source distribution (sdist)
  - Wheel distribution
  - Validates with twine
  - Uploads as artifacts

- **extract-changelog**: Extract release notes
  - Extracts version from tag
  - Parses CHANGELOG.md for version-specific notes
  - Falls back to generic message if not found

- **create-release**: Create GitHub release
  - Creates release with changelog
  - Attaches dist files (sdist + wheel)
  - Marks as prerelease if tag contains alpha/beta/rc

- **publish-pypi**: Publish to PyPI
  - Only runs for official repo (anthropics/doc-guardian)
  - Requires PYPI_API_TOKEN secret
  - Skips existing versions

- **publish-test-pypi**: Publish to Test PyPI
  - Only for prerelease tags (alpha/beta/rc)
  - Requires TEST_PYPI_API_TOKEN secret

- **verify-release**: Verify release
  - Installs from wheel
  - Verifies version
  - Tests CLI commands
  - Runs smoke test

- **release-summary**: Summary job
  - Reports status of all release jobs

**Prerelease Detection**:
Tags containing "alpha", "beta", or "rc" are marked as prereleases and published to Test PyPI only.

---

## Secrets Required

For full CI/CD functionality, configure these secrets in your GitHub repository:

| Secret | Purpose | Required For |
|--------|---------|--------------|
| `CODECOV_TOKEN` | Upload coverage to Codecov | Coverage reporting (optional) |
| `PYPI_API_TOKEN` | Publish to PyPI | Production releases |
| `TEST_PYPI_API_TOKEN` | Publish to Test PyPI | Prerelease testing (optional) |

**Setup Instructions**:

1. **Codecov**:
   - Sign up at https://codecov.io
   - Link your GitHub repository
   - Get token from Codecov settings
   - Add to GitHub Secrets as `CODECOV_TOKEN`

2. **PyPI**:
   - Create account at https://pypi.org
   - Generate API token in account settings
   - Add to GitHub Secrets as `PYPI_API_TOKEN`

3. **Test PyPI** (optional):
   - Create account at https://test.pypi.org
   - Generate API token
   - Add to GitHub Secrets as `TEST_PYPI_API_TOKEN`

---

## Badges

Add these badges to your README.md:

```markdown
[![Tests](https://github.com/anthropics/doc-guardian/workflows/Tests/badge.svg)](https://github.com/anthropics/doc-guardian/actions/workflows/test.yml)
[![Lint](https://github.com/anthropics/doc-guardian/workflows/Lint/badge.svg)](https://github.com/anthropics/doc-guardian/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/anthropics/doc-guardian/branch/main/graph/badge.svg)](https://codecov.io/gh/anthropics/doc-guardian)
```

Replace `anthropics/doc-guardian` with your repository path if forked.

---

## Release Process

### Standard Release (PyPI)

1. **Update version** in `guardian/__init__.py` and `pyproject.toml`
2. **Update CHANGELOG.md** with release notes
3. **Commit changes**: `git commit -m "Release v0.2.0"`
4. **Create tag**: `git tag v0.2.0`
5. **Push tag**: `git push origin v0.2.0`
6. **GitHub Actions will**:
   - Run all tests
   - Build distributions
   - Create GitHub release
   - Publish to PyPI
   - Verify installation

### Prerelease (Test PyPI)

For alpha/beta/rc versions:

1. **Update version**: `guardian/__init__.py` → `"0.2.0-beta.1"`
2. **Update CHANGELOG.md**
3. **Create tag**: `git tag v0.2.0-beta.1`
4. **Push tag**: `git push origin v0.2.0-beta.1`
5. **GitHub Actions will**:
   - Mark as prerelease on GitHub
   - Publish to Test PyPI (not production PyPI)

---

## Local Testing

Before pushing, run these locally to catch issues:

```bash
# Install dev dependencies
pip install -e ".[dev,all]"

# Run tests
pytest --cov=guardian --cov-report=term -v

# Run linting
ruff check guardian/ tests/ examples/
ruff format --check guardian/ tests/ examples/
black --check guardian/ tests/ examples/

# Run type checking
mypy guardian/ --ignore-missing-imports

# Validate pyproject.toml
pip install validate-pyproject
validate-pyproject pyproject.toml

# Security checks
pip install bandit safety
bandit -r guardian/
safety check
```

---

## Troubleshooting

### Tests Fail on Windows but Pass on Linux/macOS

Common causes:
- Path separator issues (use `pathlib.Path`)
- Line ending issues (CRLF vs LF)
- Case-sensitive filesystem issues

**Fix**: Use cross-platform path utilities from `pathlib`.

### Coverage Upload Fails

**Cause**: Missing `CODECOV_TOKEN` secret

**Fix**: Add secret to GitHub repository settings or disable codecov upload.

### PyPI Publish Fails

Common causes:
- Missing `PYPI_API_TOKEN` secret
- Version already exists (increment version)
- Invalid package metadata

**Fix**: Check error message in GitHub Actions logs.

### Type Checking Fails (mypy)

**Status**: Non-blocking by design

**Why**: Type hints may be incomplete in early versions.

**Fix**: Add type hints gradually. Job won't fail workflow.

### Markdown Linting Fails

**Status**: Non-blocking by design

**Fix**: Update `.markdownlint.json` config or fix markdown issues.

---

## Future Enhancements

Planned CI/CD improvements:

- [ ] Docker image build and publish
- [ ] Documentation site deployment (GitHub Pages)
- [ ] Performance benchmarking (track regression)
- [ ] Integration test suite (full end-to-end)
- [ ] Automatic dependency updates (Dependabot)
- [ ] Security scanning (CodeQL)
- [ ] Release notes generation from commit history

---

## Contributing

When adding new CI/CD features:

1. Test locally first with `act` (GitHub Actions local runner)
2. Use conditional logic to avoid breaking existing workflows
3. Mark experimental jobs as non-blocking (continue-on-error)
4. Update this documentation
5. Test with a fork before merging to main

---

**Last Updated**: 2026-01-11
