# Changelog

All notable changes to Doc Guardian will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release preparation
- Comprehensive test suite with 95%+ coverage
- Security hardening (path traversal prevention, regex validation)
- Performance benchmarks
- Custom healer development guide

## [0.1.0] - 2026-01-11

### Added
- **Core Framework**
  - Confidence-based healing system (4-factor model)
  - Git-integrated rollback support
  - Atomic file operations with crash recovery
  - Structured logging with rotation

- **7 Built-in Healers**
  - `fix_broken_links` - Fuzzy-match and repair broken internal links
  - `detect_staleness` - Flag documents older than configured threshold
  - `resolve_duplicates` - Identify and consolidate duplicate content
  - `balance_references` - Maintain bidirectional links
  - `sync_canonical` - Sync docs from source schemas (JSON/YAML/TOML)
  - `manage_collapsed` - Auto-collapse long sections with `<details>` tags
  - `enforce_disclosure` - Enforce progressive disclosure architecture

- **Configuration**
  - TOML-based configuration with extensive validation
  - Per-healer configuration options
  - Confidence threshold customization
  - Git integration settings

- **Utilities**
  - `heal.py` - Main healing orchestrator
  - `install.py` - Git hooks installer
  - `rollback.py` - Change rollback utility

- **Documentation**
  - README with quick start guide
  - Configuration guide
  - Custom healer development guide
  - Per-healer usage documentation

### Security
- Path traversal prevention in all file operations
- Regex pattern validation to prevent ReDoS
- Secure temporary file handling
- No external API calls (fully local processing)

---

[Unreleased]: https://github.com/anthropics/doc-guardian/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/anthropics/doc-guardian/releases/tag/v0.1.0
