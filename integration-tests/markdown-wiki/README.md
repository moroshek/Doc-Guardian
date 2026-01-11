# Markdown Wiki Integration Test

This is an integration test project for Doc Guardian demonstrating documentation quality checks on a typical markdown-based wiki.

## About This Project

**DataFlow** is a fictional data processing framework (similar to Apache Flink or Spark Streaming). This documentation wiki contains:
- Getting started guides
- User and administrator documentation
- API and CLI reference
- Contributing guidelines

The wiki intentionally includes various documentation issues that Doc Guardian can detect and fix.

## Intentional Issues

This wiki includes the following intentional issues for Doc Guardian to catch:

### 1. Broken Links
- `user-guide.md` references non-existent files:
  - `connectors.md` (should be in same directory)
  - `../guides/patterns-guide.md` (doesn't exist)
  - `../operations/deployment-guide.md` (wrong path, actually `../guides/admin-guide.md`)
  - `../guides/security.md` (doesn't exist)
  - `advanced-patterns.md` (doesn't exist)
  - `performance.md` (doesn't exist)

- `quick-start.md` references:
  - `config.md` (should be `configuration.md`)
  - `../guides/user-manual.md` (doesn't exist, should be `user-guide.md`)

- `api.md` references:
  - `../guides/patterns-guide.md` (doesn't exist)
  - `../reference/environment.md` (doesn't exist)
  - `migration-v2.md` (doesn't exist)

- `config.md` references:
  - `../guides/security-config.md` (doesn't exist, should be admin-guide security section)

- `development.md` references:
  - `../contributing/CONTRIBUTING.md` (doesn't exist)
  - `../architecture/overview.md` (doesn't exist)
  - `../architecture/design.md` (doesn't exist)

### 2. Stale Timestamps
Some files have old `Last Updated` dates:
- `quick-start.md`: 2024-08-15 (5 months old)
- `configuration.md`: 2024-10-20 (3 months old)
- `troubleshooting.md`: 2024-11-28 (2 months old)

These are older than the 90-day threshold in `config.toml`.

### 3. Missing Collapsed Sections
Several files have very long sections that could benefit from `<details>` tags:
- `user-guide.md`: Long "Transformations" and "Windowing" sections
- `admin-guide.md`: Long "Deployment" and "Monitoring" sections
- `troubleshooting.md`: Long "Common Issues" section with many subsections

### 4. Duplicate Content
Some content is intentionally duplicated across files (typical in wikis where examples are repeated):
- Kafka configuration examples appear in multiple places
- Database connection examples are similar across files
- Some CLI commands are repeated

Note: `resolve_duplicates` healer is disabled by default for wikis.

## Setup

```bash
# Create guardian symlink (required to run healers)
ln -s ../../guardian guardian

# Or if running from doc-guardian root:
cd integration-tests/markdown-wiki
ln -s ../../guardian guardian
```

## Running Doc Guardian

### Audit Mode (Read-only)

Check for issues without making changes:

```bash
cd doc-guardian/integration-tests/markdown-wiki
cargo run --bin doc-guardian -- audit
```

Expected output:
- 10+ broken links detected
- 3 files flagged as stale
- Multiple sections suggested for collapse

### Heal Mode (Apply Fixes)

Fix detected issues:

```bash
cargo run --bin doc-guardian -- heal
```

This will:
- Suggest fixes for broken links (with fuzzy matching)
- Update stale timestamps to current date
- Add `<details>` tags to long sections
- Generate a report of changes

### Verify Mode

After healing, verify all issues are resolved:

```bash
cargo run --bin doc-guardian -- verify
```

Should report no remaining issues.

## Expected Healer Behavior

### fix_broken_links

Should detect and suggest fixes for:
- `connectors.md` → Suggest creating it or linking elsewhere
- `patterns-guide.md` → No close match, suggest removal
- `deployment-guide.md` → Suggest `admin-guide.md` (fuzzy match)
- `config.md` → Suggest `configuration.md` (close match)
- `user-manual.md` → Suggest `user-guide.md` (fuzzy match)

### detect_staleness

Should flag:
- `quick-start.md` (162 days old)
- `configuration.md` (82 days old)
- `troubleshooting.md` (44 days old - just over threshold)

And update their `Last Updated:` timestamps.

### manage_collapsed

Should suggest collapsing:
- User guide: Transformations section (~80 lines)
- User guide: Windowing section (~70 lines)
- Admin guide: Deployment section (~100 lines)
- Admin guide: Monitoring section (~90 lines)
- Troubleshooting: Common Issues section (~150 lines)

## Configuration

See `config.toml` for Doc Guardian settings:

```toml
[healers.fix_broken_links]
enabled = true
fuzzy_threshold = 0.85

[healers.detect_staleness]
enabled = true
max_staleness_days = 90

[healers.manage_collapsed]
enabled = true
min_section_lines = 20

[healers.resolve_duplicates]
enabled = false  # Disabled for wikis
```

## Project Structure

```
markdown-wiki/
├── README.md (this file)
├── config.toml (Doc Guardian config)
└── docs/
    ├── index.md
    ├── getting-started/
    │   ├── installation.md
    │   ├── quick-start.md (has stale date)
    │   └── configuration.md (has stale date)
    ├── guides/
    │   ├── user-guide.md (has broken links)
    │   ├── admin-guide.md
    │   └── troubleshooting.md (has stale date)
    ├── reference/
    │   ├── api.md (has broken links)
    │   ├── cli.md
    │   └── config.md (has broken links)
    └── contributing/
        ├── development.md (has broken links)
        ├── testing.md
        └── code-style.md
```

## Success Criteria

After running healers, verify:

1. **All links resolve** - No 404s when clicking through docs
2. **Dates are current** - All `Last Updated` timestamps within 90 days
3. **Long sections collapsed** - Sections over 20 lines have `<details>` tags
4. **No duplicate warnings** - Intentional duplication is acceptable

## Notes

- This is a realistic documentation structure for an open-source project
- The content is complete enough to test contextual understanding
- Issues are subtle enough to require intelligent healing (not just find/replace)
- The wiki structure tests cross-directory link resolution

## Integration with Test Suite

This example should be integrated into Doc Guardian's integration test suite:

```bash
# Run all integration tests
cargo test --test integration_tests

# Run just the markdown-wiki test
cargo test --test integration_tests markdown_wiki
```

The test should:
1. Run audit mode and verify expected issues are detected
2. Run heal mode and apply fixes
3. Verify all issues are resolved
4. Check that fixes are sensible (not breaking the content)
