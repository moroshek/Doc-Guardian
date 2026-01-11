# Workflow Architecture

Visual guide to Doc Guardian's CI/CD workflow architecture.

---

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DOC GUARDIAN CI/CD                              │
│                                                                       │
│  Push/PR to main/develop          Tag Push (v*)                     │
│          ↓                              ↓                            │
│  ┌───────┴───────┐              ┌──────┴──────┐                    │
│  │               │              │              │                     │
│  │  test.yml     │              │ release.yml │                     │
│  │  lint.yml     │──────────────→              │                     │
│  │               │   Must pass  │              │                     │
│  └───────────────┘              └──────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Execution Flow

### On Push/PR (Parallel Execution)

```
                    GitHub Push/PR Event
                            ↓
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
   ┌─────────┐         ┌─────────┐        ┌─────────┐
   │test.yml │         │lint.yml │        │         │
   │(~10 min)│         │(~5 min) │        │ Other   │
   └────┬────┘         └────┬────┘        │ Actions │
        │                   │              └─────────┘
        │                   │
        ├─────────┬─────────┤
        ↓         ↓         ↓
     ┌─────┐  ┌─────┐  ┌─────┐
     │ All │  │ All │  │     │
     │Pass?│  │Pass?│  │     │
     └──┬──┘  └──┬──┘  └─────┘
        │        │
        └────┬───┘
             ↓
      ✅ Ready to Merge
```

---

## test.yml - Test Workflow

```
test.yml Trigger (push/PR)
         ↓
    ┌────┴────────────────────────────────────┐
    │                                          │
    ↓                   ↓                      ↓
┌───────┐         ┌────────────┐         ┌──────────┐
│ test  │         │ test-opt   │         │ test-    │
│ (15x) │         │ -deps (4x) │         │ parallel │
└───┬───┘         └─────┬──────┘         └────┬─────┘
    │                   │                     │
    │     Python 3.8-3.12                     │
    │     ubuntu/macos/win                    │
    │                   │                     │
    │                   ↓                     │
    │           ┌──────────────┐              │
    │           │ integration- │              │
    │           │     test     │              │
    │           └──────┬───────┘              │
    │                  │                      │
    └──────────────────┴──────────────────────┘
                       ↓
               ┌──────────────┐
               │ test-summary │
               │ (aggregate)  │
               └──────┬───────┘
                      ↓
              ✅ All tests pass
                      or
              ❌ Report failures
```

### Test Job Matrix

```
┌─────────────┬──────┬──────┬──────┬──────┬──────┐
│ OS / Python │ 3.8  │ 3.9  │ 3.10 │ 3.11 │ 3.12 │
├─────────────┼──────┼──────┼──────┼──────┼──────┤
│ ubuntu      │  ✓   │  ✓   │  ✓   │  ✓   │  ✓   │
│ macos       │  ✓   │  ✓   │  ✓   │  ✓   │  ✓   │
│ windows     │  ✓   │  ✓   │  ✓   │  ✓   │  ✓   │
└─────────────┴──────┴──────┴──────┴──────┴──────┘

Total: 15 test combinations
Special: ubuntu+3.11 uploads coverage
```

---

## lint.yml - Linting Workflow

```
lint.yml Trigger (push/PR)
         ↓
    ┌────┴────────────────────────────────────────────┐
    │                                                  │
    ↓           ↓           ↓           ↓              ↓
┌──────┐   ┌───────┐   ┌──────┐   ┌────────┐   ┌──────────┐
│ ruff │   │ black │   │ mypy │   │markdown│   │pyproject │
│      │   │       │   │      │   │  -lint │   │-validate │
└──┬───┘   └───┬───┘   └──┬───┘   └───┬────┘   └────┬─────┘
   │           │          │            │             │
CRITICAL    CRITICAL   OPTIONAL    OPTIONAL      CRITICAL
   │           │          │            │             │
   └───────────┴──────────┴────────────┴─────────────┘
                          ↓
                   ┌────────────┐
                   │  security  │
                   │  (bandit/  │
                   │  safety)   │
                   └─────┬──────┘
                         │
                     OPTIONAL
                         ↓
                  ┌────────────┐
                  │lint-summary│
                  └──────┬─────┘
                         ↓
              Critical checks pass?
                    ✅ Yes → Pass
                    ❌ No  → Fail
            (Optional failures = warnings)
```

### Failure Behavior

```
Critical Failures (Block merge):
  • ruff check fails
  • black format check fails
  • pyproject.toml invalid

Non-Critical Failures (Report only):
  • mypy type errors
  • markdownlint issues
  • security warnings
```

---

## release.yml - Release Workflow

```
Tag Push (v*)
     ↓
┌─────────────┐
│   build     │ ← Build sdist + wheel
└──────┬──────┘
       ↓
┌─────────────┐
│extract-     │ ← Parse CHANGELOG.md
│changelog    │
└──────┬──────┘
       ↓
┌─────────────┐
│create-      │ ← Create GitHub Release
│release      │   Attach dist files
└──────┬──────┘
       ↓
       ├──────────────────────┐
       ↓                      ↓
┌─────────────┐      ┌──────────────┐
│publish-     │      │publish-test- │
│pypi         │      │pypi          │
│(stable)     │      │(prerelease)  │
└──────┬──────┘      └──────┬───────┘
       │                    │
       └──────────┬─────────┘
                  ↓
           ┌──────────────┐
           │verify-release│ ← Smoke test
           └──────┬───────┘
                  ↓
           ┌──────────────┐
           │release-      │
           │summary       │
           └──────────────┘
```

### Release Decision Tree

```
Tag pushed: v*
     ↓
Is tag format vX.Y.Z?
     ├─ NO → Workflow skipped
     └─ YES
         ↓
Contains alpha/beta/rc?
     ├─ YES → Prerelease
     │         ↓
     │    Mark as prerelease
     │    Publish to Test PyPI
     │         ↓
     │    ✅ Done
     │
     └─ NO → Stable Release
               ↓
          Publish to PyPI
               ↓
          ✅ Done
```

---

## Data Flow

### Test Coverage Flow

```
Test runs on ubuntu+3.11
         ↓
   pytest --cov
         ↓
  coverage.xml generated
         ↓
Upload to Codecov
         ↓
Generate coverage badge
         ↓
Badge artifact saved
         ↓
   ✅ Coverage tracked
```

### Build Artifact Flow

```
Release triggered
         ↓
python -m build
         ↓
dist/
  ├── doc-guardian-0.2.0.tar.gz
  └── doc_guardian-0.2.0-py3-none-any.whl
         ↓
Validate with twine
         ↓
Upload to GitHub Release
         ↓
Publish to PyPI
         ↓
   ✅ Package available
```

---

## Parallel Execution

### test.yml Parallelism

```
             Test Workflow Starts
                      ↓
        ┌─────────────┼─────────────┐
        │             │             │
        ↓             ↓             ↓
   Matrix Job    Optional Deps  Parallel
   (15 runners)   (4 runners)   (1 runner)
        │             │             │
        └─────────────┴─────────────┘
                      ↓
              Integration Tests
                   (1 runner)
                      ↓
                All jobs done
               (runs in ~10 min)
```

### lint.yml Parallelism

```
           Lint Workflow Starts
                    ↓
    ┌───────────────┼───────────────┐
    ↓       ↓       ↓       ↓       ↓
  ruff   black   mypy  markdown  pyproject
    │       │       │       │       │
    └───────┴───────┴───────┴───────┘
                    ↓
                security
                    ↓
              All jobs done
             (runs in ~5 min)
```

---

## Error Handling

### Failure Propagation

```
Job Fails
    ↓
Is job critical?
    ├─ YES → Mark workflow as failed
    │         ↓
    │    Block merge/release
    │         ↓
    │    Send notification
    │
    └─ NO → Continue workflow
              ↓
         Report in summary
              ↓
         ⚠️ Warning only
```

### Retry Behavior

```
Job fails
    ↓
Is it transient? (network, timeout)
    ├─ YES → Auto-retry (GitHub default: 0)
    │         Manual retry available
    │
    └─ NO → Permanent failure
              ↓
         Report error
              ↓
         Manual intervention needed
```

---

## Secret Usage

```
┌──────────────────────────────────────────────┐
│               GitHub Secrets                  │
│                                               │
│  CODECOV_TOKEN ──────→ test.yml (coverage)   │
│  PYPI_API_TOKEN ─────→ release.yml (pypi)    │
│  TEST_PYPI_API_TOKEN → release.yml (test)    │
│                                               │
│  Encrypted at rest                           │
│  Masked in logs                              │
│  Scoped to workflows                         │
└──────────────────────────────────────────────┘
```

---

## Trigger Matrix

| Event Type | test.yml | lint.yml | release.yml |
|------------|----------|----------|-------------|
| Push to main | ✅ | ✅ | ❌ |
| Push to develop | ✅ | ✅ | ❌ |
| Pull Request | ✅ | ✅ | ❌ |
| Tag Push (v*) | ❌ | ❌ | ✅ |
| Manual (workflow_dispatch) | ➖ | ➖ | ➖ |

➖ = Can be added if needed

---

## Job Dependencies

### test.yml Dependencies

```
test ──┐
test-optional-deps ──┼──→ test-summary
test-parallel ──┤
integration-test ──┘

No dependencies between first 4 jobs (run in parallel)
Summary job waits for all 4
```

### lint.yml Dependencies

```
ruff ──┐
black ──┤
mypy ──┼──→ lint-summary
markdown-lint ──┤
pyproject-validate ──┤
security ──┘

No dependencies between first 6 jobs (run in parallel)
Summary job waits for all 6
```

### release.yml Dependencies

```
build ──→ extract-changelog ──→ create-release ──→ publish-pypi
                                      │
                                      └──→ publish-test-pypi
                                      │
                                      └──→ verify-release ──→ release-summary
```

---

## Performance Characteristics

| Workflow | Jobs | Duration | Parallelism | Cost (minutes) |
|----------|------|----------|-------------|----------------|
| test.yml | 5 | ~10 min | 15 runners | ~20 min |
| lint.yml | 7 | ~5 min | 6 runners | ~6 min |
| release.yml | 7 | ~8 min | Sequential | ~8 min |

**Total per PR**: ~15 minutes real time, ~26 compute minutes
**Total per release**: ~8 minutes real time, ~8 compute minutes

---

## Caching Strategy

```
┌─────────────────────────────────────────┐
│           Dependency Caching             │
│                                          │
│  actions/setup-python@v5                │
│       ↓                                  │
│  Cache key: ${{ runner.os }}-pip-...    │
│       ↓                                  │
│  Cached: ~/.cache/pip                   │
│       ↓                                  │
│  Speedup: 30-60s per job                │
│                                          │
│  Cache invalidates when:                │
│    • pyproject.toml changes             │
│    • requirements change                │
│    • Weekly (GitHub default)            │
└─────────────────────────────────────────┘
```

---

## Monitoring & Alerts

```
Workflow Run
     ↓
Status Change
     ↓
     ├──→ Success → Update badge (green)
     │
     ├──→ Failure → Update badge (red)
     │              Email notification
     │              GitHub notification
     │
     └──→ Cancelled → Update badge (grey)
```

---

**Reference**: See `.github/CI_CD.md` for detailed documentation.

**Last Updated**: 2026-01-11
