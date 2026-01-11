# Workflow Comparison

This document compares the existing `ci.yml` workflow with the new modular workflows.

## Summary

**Existing**: `ci.yml` (single workflow)
**New**: `test.yml`, `lint.yml`, `release.yml` (modular approach)

---

## Comparison

| Feature | Existing (ci.yml) | New (test.yml + lint.yml + release.yml) |
|---------|-------------------|------------------------------------------|
| **Testing** | ✅ Full matrix | ✅ Full matrix + optional deps + parallel |
| **Linting** | ✅ Basic (ruff only) | ✅ Comprehensive (ruff + black + markdown + security) |
| **Type checking** | ✅ mypy (non-blocking) | ✅ mypy (non-blocking) |
| **Coverage** | ✅ Codecov upload | ✅ Codecov upload + badge generation |
| **Build** | ✅ Basic build | ✅ Full build with verification |
| **Integration tests** | ✅ Yes | ❌ Not included (can add) |
| **Release automation** | ❌ None | ✅ Full release + PyPI publish |
| **Markdown linting** | ❌ None | ✅ markdownlint-cli |
| **Security checks** | ❌ None | ✅ bandit + safety |
| **pyproject validation** | ❌ None | ✅ validate-pyproject |
| **Modular triggers** | Single workflow | Separate workflows (faster feedback) |

---

## Advantages of New Workflows

### 1. Modularity
- **Faster feedback**: Lint failures show up immediately without waiting for full test matrix
- **Easier debugging**: Clear separation of concerns
- **Selective reruns**: Can rerun just linting or just tests

### 2. Comprehensive Linting
- **ruff**: Python linting
- **black**: Code formatting
- **markdownlint**: Documentation quality
- **bandit**: Security scanning
- **safety**: Dependency vulnerability checking
- **pyproject validation**: Metadata correctness

### 3. Release Automation
- **GitHub releases**: Automatic release creation
- **PyPI publishing**: Automated package publishing
- **Changelog extraction**: Auto-extracts release notes
- **Prerelease support**: Alpha/beta/rc handling
- **Verification**: Post-release smoke tests

### 4. Better Organization
- Clear job summaries
- Non-critical checks don't block (mypy, markdown, security)
- Critical checks must pass (ruff, black, pyproject)

---

## Advantages of Existing Workflow

### 1. Simplicity
- Single file to maintain
- All CI in one place

### 2. Integration Tests
- Tests integration-test projects
- Validates end-to-end functionality

---

## Recommendation

**Option 1: Replace ci.yml with new workflows** (RECOMMENDED)
- More features
- Better organization
- Industry standard pattern
- Need to add integration test job to test.yml

**Option 2: Keep both**
- Rename ci.yml to legacy-ci.yml
- Disable by changing trigger to `workflow_dispatch` only
- Keep as fallback

**Option 3: Merge**
- Keep ci.yml as main test workflow
- Add lint.yml and release.yml as separate workflows
- Remove linting from ci.yml (avoid duplication)

---

## Migration Plan (Option 1)

1. **Add integration tests to test.yml**:
   ```yaml
   integration-test:
     name: Integration Tests
     runs-on: ubuntu-latest
     steps:
       - name: Checkout code
         uses: actions/checkout@v4
       - name: Set up Python
         uses: actions/setup-python@v5
         with:
           python-version: '3.11'
       - name: Install package
         run: pip install -e ".[all]"
       - name: Run integration tests
         run: |
           for project in integration-tests/*/; do
             if [ -f "${project}config.toml" ]; then
               echo "Testing ${project}..."
               python guardian/heal.py --config "${project}config.toml" --check
             fi
           done
   ```

2. **Rename ci.yml to ci-legacy.yml**

3. **Update README badges** (already done)

4. **Test new workflows** on a feature branch first

5. **Archive ci-legacy.yml** after confirming new workflows work

---

## Quick Decision Matrix

| Your Priority | Recommendation |
|---------------|----------------|
| **Maximum features** | Use new workflows (Option 1) |
| **Minimal change** | Keep existing ci.yml |
| **Gradual migration** | Add lint.yml + release.yml, keep ci.yml for tests (Option 3) |
| **Industry standard** | Use new workflows (Option 1) |

---

## Files

### Existing
- `.github/workflows/ci.yml` - Combined CI workflow

### New
- `.github/workflows/test.yml` - Testing (unit + integration + coverage)
- `.github/workflows/lint.yml` - Linting (code + docs + security)
- `.github/workflows/release.yml` - Release automation (GitHub + PyPI)
- `.github/CI_CD.md` - Documentation
- `.markdownlint.json` - Markdown linting config

---

**Recommendation**: Implement Option 1 (replace with new workflows) for best long-term maintainability and features.
