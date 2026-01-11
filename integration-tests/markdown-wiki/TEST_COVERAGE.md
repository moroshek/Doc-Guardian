# Test Coverage Summary

This document lists all intentional issues planted in the markdown-wiki for Doc Guardian testing.

## Issue Summary

| Issue Type | Count | Files Affected |
|------------|-------|----------------|
| Broken Links | 11 | 5 files |
| Stale Timestamps | 3 | 3 files |
| Long Sections | 5+ | 3 files |

## Detailed Issues

### 1. Broken Links (11 total)

#### user-guide.md (4 broken links)
- Line 46: `[Connector Guide](connectors.md)` → File doesn't exist
- Line 453: `[advanced patterns](advanced-patterns.md)` → File doesn't exist
- Line 452: `[deployment](../operations/deployment-guide.md)` → Wrong path (should be `../guides/admin-guide.md`)
- Line 454: `[performance tuning guide](performance.md)` → File doesn't exist

#### quick-start.md (2 broken links)
- Line 108: `[Configuration Guide](config.md)` → Should be `configuration.md`
- Line 113: `[windowing and aggregation](../guides/user-manual.md#windowing)` → File doesn't exist (should be `user-guide.md`)

#### api.md (2 broken links)
- Line 604: `[Migration Guide](migration-v2.md)` → File doesn't exist
- Line 611: `[Configuration Reference](../reference/environment.md)` → File doesn't exist

#### config.md (1 broken link)
- Line 582: `[Security Guide](../guides/security-config.md)` → File doesn't exist

#### development.md (2 broken links)
- Line 365: `[Architecture Overview](../architecture/overview.md)` → Directory doesn't exist
- Line 366: `[Architecture Docs](../architecture/design.md)` → Directory doesn't exist

### 2. Stale Timestamps (3 files)

#### quick-start.md
```markdown
**Last Updated:** 2024-08-15
```
- **Age**: ~149 days (as of 2025-01-10)
- **Status**: Over 90-day threshold

#### configuration.md
```markdown
**Last Updated:** 2024-10-20
```
- **Age**: ~82 days
- **Status**: Just under threshold (edge case for testing)

#### troubleshooting.md
```markdown
**Last Updated:** 2024-11-28
```
- **Age**: ~43 days
- **Status**: Under threshold but getting close

### 3. Long Sections Needing Collapse

#### user-guide.md
1. **Transformations section** (lines ~115-195, ~80 lines)
   - Contains map, filter, flat_map, reduce subsections
   - Should be collapsed for better scannability

2. **Windowing section** (lines ~197-267, ~70 lines)
   - Contains tumbling, sliding, session windows
   - Should be collapsed

#### admin-guide.md
1. **Deployment section** (lines ~22-155, ~133 lines)
   - Contains Kubernetes, Docker, Bare Metal deployment
   - Excellent candidate for collapse

2. **Monitoring section** (lines ~157-282, ~125 lines)
   - Contains metrics, logging, tracing, dashboards
   - Should be collapsed

#### troubleshooting.md
1. **Common Issues section** (lines ~18-282, ~264 lines)
   - Massive section with many subsections
   - Definitely needs collapsing

### 4. Cross-file Link Patterns

#### Valid Links (Should Pass)
- `[Installation](installation.md)` → Same directory, exists
- `[User Guide](../guides/user-guide.md)` → Cross-directory, exists
- `[API Reference](../reference/api.md)` → Cross-directory, exists

#### Invalid Links (Should Fail)
- `[Missing File](missing.md)` → Same directory, doesn't exist
- `[Wrong Path](../wrong/path.md)` → Directory doesn't exist
- `[Typo](confiuration.md)` → Close to `configuration.md`, fuzzy match candidate

## Expected Healer Behavior

### fix_broken_links

**Should detect:**
- All 11 broken links listed above

**Should suggest:**
- `connectors.md` → Create file or link to existing connector docs
- `config.md` → `configuration.md` (0.92 similarity, high confidence)
- `user-manual.md` → `user-guide.md` (0.85 similarity, fuzzy match)
- `deployment-guide.md` → `admin-guide.md` (contains deployment info)
- Files with no close matches → Flag for manual review

**Should NOT suggest:**
- Links to external URLs (github.com, discord.gg)
- Links to anchors in valid files (`user-guide.md#windowing`)

### detect_staleness

**Should flag:**
- `quick-start.md` (149 days old) - HIGH PRIORITY
- `configuration.md` (82 days old) - MEDIUM PRIORITY
- `troubleshooting.md` (43 days old) - LOW PRIORITY (optional)

**Should update:**
- Change `Last Updated: 2024-08-15` to current date
- Preserve formatting (bold, spacing)

**Should NOT flag:**
- `installation.md` (2025-01-10) - Current
- `api.md` (2025-01-10) - Current

### manage_collapsed

**Should collapse sections with:**
- 20+ lines (configurable threshold)
- Clear section headers (##, ###)
- Self-contained content

**Expected transformations:**
```markdown
## Long Section

[80 lines of content]
```

Becomes:

```markdown
## Long Section

<details>
<summary>Click to expand</summary>

[80 lines of content]

</details>
```

**Should preserve:**
- Code blocks within collapsed sections
- Links and formatting
- Nested subsections

## Test Validation

After running healers, verify:

1. **Broken Links**
   - [ ] All broken links detected
   - [ ] Fuzzy matches suggested for similar filenames
   - [ ] No false positives on valid links

2. **Stale Timestamps**
   - [ ] 3 files flagged as stale
   - [ ] Timestamps updated to current date
   - [ ] Formatting preserved

3. **Collapsed Sections**
   - [ ] 5+ sections collapsed
   - [ ] Content preserved and readable
   - [ ] No broken formatting

4. **No Regressions**
   - [ ] Valid links still work
   - [ ] Current files not flagged as stale
   - [ ] Short sections not collapsed

## Integration Test Assertions

```rust
#[test]
fn test_markdown_wiki_issues() {
    let report = run_audit("integration-tests/markdown-wiki");

    // Broken links
    assert_eq!(report.broken_links.len(), 11);
    assert!(report.has_broken_link("user-guide.md", "connectors.md"));
    assert!(report.has_broken_link("quick-start.md", "config.md"));

    // Stale files
    assert_eq!(report.stale_files.len(), 3);
    assert!(report.is_stale("quick-start.md"));

    // Long sections
    assert!(report.sections_to_collapse.len() >= 5);
    assert!(report.should_collapse("user-guide.md", "Transformations"));
}

#[test]
fn test_markdown_wiki_healing() {
    let result = run_heal("integration-tests/markdown-wiki");

    assert!(result.success);
    assert_eq!(result.broken_links_suggested, 11);
    assert_eq!(result.stale_files_updated, 3);
    assert!(result.sections_collapsed >= 5);
}
```

## Notes

- This test covers realistic documentation scenarios
- Issues are subtle enough to test healer intelligence
- Good mix of easy fixes (typos) and complex cases (missing files)
- Tests cross-directory link resolution
- Includes edge cases (files near staleness threshold)
