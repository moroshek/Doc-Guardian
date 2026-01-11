# Configuration Reference

**Last Updated**: 2026-01-11

---

## Minimal Config

```toml
[project]
root = "."
doc_root = "docs/"
```

---

## [project]

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `name` | string | No | - | Project name |
| `root` | path | **Yes** | - | Project root (supports `~`) |
| `doc_root` | path | **Yes** | - | Docs directory (relative to root, no `..`) |
| `excluded_dirs` | list | No | `[]` | Glob patterns to exclude |
| `excluded_files` | list | No | `[]` | Glob patterns to exclude |

---

## [confidence]

| Key | Type | Default | Range | Description |
|-----|------|---------|-------|-------------|
| `auto_commit_threshold` | float | 0.90 | 0.0-1.0 | Auto-commit if confidence >= value |
| `auto_stage_threshold` | float | 0.80 | 0.0-1.0 | Auto-stage if confidence >= value |
| `report_only_threshold` | float | 0.50 | 0.0-1.0 | Report only if confidence >= value |

### [confidence.weights]

Must sum to 1.0.

| Key | Default | Description |
|-----|---------|-------------|
| `pattern` | 0.40 | Pattern matching quality |
| `magnitude` | 0.30 | Change size (smaller = higher) |
| `risk` | 0.20 | Risk level (lower = higher) |
| `history` | 0.10 | Historical success rate |

---

## Execution Order

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `healer_order` | list | See below | Custom healer execution order |

Default order:
```toml
healer_order = [
    "sync_canonical",
    "fix_broken_links",
    "detect_staleness",
    "resolve_duplicates",
    "balance_references",
    "manage_collapsed",
    "enforce_disclosure"
]
```

**Example**: Run broken links first:
```toml
healer_order = [
    "fix_broken_links",
    "detect_staleness",
    "sync_canonical"
]
```

---

## Healers

All healers support `enabled = true|false` (default: `true`).

### [healers.fix_broken_links]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `link_pattern` | regex | `'\[([^\]]+)\]\(([^\)]+)\)'` | Markdown link pattern |
| `fuzzy_threshold` | float | 0.80 | Min similarity for fuzzy match |
| `handle_anchors` | bool | true | Validate `#anchor` links |
| `file_extensions` | list | `[".md", ".rst", ".html", ".txt"]` | Extensions to scan |

**[healers.fix_broken_links.validation]**

| Key | Default | Description |
|-----|---------|-------------|
| `check_external_links` | false | Validate HTTP/HTTPS links |
| `external_timeout_seconds` | 5 | Timeout for external checks |
| `cache_external_results` | true | Cache results for 24h |

### [healers.detect_staleness]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `timestamp_patterns` | list[regex] | See below | Patterns to detect dates |
| `staleness_threshold_days` | int | 30 | Days before flagging stale |
| `deprecated_patterns` | list | `[]` | Deprecated content patterns |
| `auto_update_timestamp` | bool | true | Auto-update timestamps |
| `timestamp_output_format` | string | `"%Y-%m-%d"` | strftime format |

Default timestamp patterns: `'\*\*Last Updated\*\*:\s*(\d{4}-\d{2}-\d{2})'`, `'Last Updated:\s*(\d{4}-\d{2}-\d{2})'`

### [healers.resolve_duplicates]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `similarity_threshold` | float | 0.80 | Duplicate detection threshold |
| `min_block_size` | int | 100 | Min chars to consider |
| `hierarchy_rules` | list | `["README.md", "docs/index.md", ...]` | Priority order |

**[healers.resolve_duplicates.detection]**

| Key | Default | Description |
|-----|---------|-------------|
| `ignore_whitespace` | true | Normalize whitespace |
| `ignore_case` | false | Case-sensitive compare |
| `min_word_count` | 20 | Min words in block |

### [healers.balance_references]

Default: `enabled = false`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `backlink_format` | string | `"**Related**: [{title}]({path})"` | Template (NOT regex) |
| `related_section_headers` | list | `["Related", "See Also", ...]` | Where to add backlinks |

**[healers.balance_references.placement]**

| Key | Default | Description |
|-----|---------|-------------|
| `prefer_existing_section` | true | Use existing Related section |
| `create_section_if_missing` | true | Create new section |
| `section_position` | `"end"` | `"start"`, `"end"`, or `"after_toc"` |

### [healers.manage_collapsed]

Default: `enabled = false`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `hint_strategy` | enum | `"summary"` | `"summary"`, `"first_sentence"`, `"keywords"` |
| `long_section_threshold` | int | 500 | Lines before collapsing |

**[healers.manage_collapsed.rules]**

| Key | Description |
|-----|-------------|
| `always_collapse` | Regex patterns to always collapse |
| `never_collapse` | Regex patterns to never collapse |

### [healers.sync_canonical]

Default: `enabled = false`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `source_file` | path | **Required** | Canonical source file |
| `source_format` | enum | `"json"` | `"json"`, `"yaml"`, `"toml"` |
| `target_patterns` | list[glob] | `[]` | Target file patterns |
| `sync_strategy` | enum | `"template"` | `"template"`, `"direct_replace"`, `"section_update"` |

### [healers.enforce_disclosure]

Default: `enabled = false`

**[healers.enforce_disclosure.layers.<name>]**

| Key | Description |
|-----|-------------|
| `max_lines` | Hard limit on file size |
| `allowed_depth` | Max heading depth |
| `file_patterns` | Glob patterns for this layer |
| `required_sections` | Headers that must exist |

**[healers.enforce_disclosure.violations]**

| Key | Default | Description |
|-----|---------|-------------|
| `action` | `"warn"` | `"warn"`, `"error"`, `"auto_split"` |
| `auto_split_threshold` | 1.5 | Split if exceeds max_lines by factor |

---

## [git]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `auto_commit` | bool | true | Auto-commit high-confidence changes |
| `commit_prefix` | string | `"[docs]"` | Commit message prefix |
| `install_hooks` | bool | true | Install git hooks |
| `hooks` | list | `["post-commit", "pre-push"]` | Hooks to install |

---

## [reporting]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `format` | enum | `"markdown"` | `"markdown"`, `"json"`, or `"both"` (markdown+json) |
| `output_dir` | path | `"reports/"` | Report directory |
| `include_confidence` | bool | true | Include confidence scores |
| `verbose` | bool | false | Verbose logging |

**[reporting.thresholds]**

| Key | Default | Description |
|-----|---------|-------------|
| `min_confidence_to_report` | 0.50 | Min confidence to include |
| `max_findings_per_report` | 100 | Max findings per report |

---

## [advanced]

| Key | Status | Default | Description |
|-----|--------|---------|-------------|
| `dry_run` | Implemented | false | Analyze without modifying |
| `max_workers` | NOT IMPL | 0 | Parallel workers (0=auto) |
| `cache_dir` | NOT IMPL | `.doc-guardian-cache/` | Cache directory |

**[advanced.logging]**

| Key | Default | Description |
|-----|---------|-------------|
| `level` | `"INFO"` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` |
| `log_file` | `"doc-guardian.log"` | Log file path |

---

## Resource Limits (Hardcoded)

| Resource | Limit |
|----------|-------|
| Max patterns per list | 1000 |
| Max regex length | 10000 chars |
| Max path length | 4096 chars |
| Max config size | 100 MB |
| Max doc file size | 10 MB |
| Max nesting depth | 20 levels |

---

## Example: Production Config

```toml
[project]
name = "my-project"
root = "."
doc_root = "docs/"
excluded_dirs = [".git", "node_modules", "venv"]

[confidence]
auto_commit_threshold = 0.95
auto_stage_threshold = 0.85

[healers.fix_broken_links]
enabled = true
fuzzy_threshold = 0.85

[healers.detect_staleness]
enabled = true
staleness_threshold_days = 60

[git]
auto_commit = true
commit_prefix = "[docs]"

[reporting]
format = "both"
output_dir = "reports/"
```

---

## See Also

- [CLI Reference](CLI.md)
- [API Reference](API.md)
