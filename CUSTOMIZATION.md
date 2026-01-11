# Doc Guardian Customization

## Quick Start Configs

**Minimal** (30 sec):
```toml
[project]
root = "."
doc_root = "docs/"

[healers.fix_broken_links]
enabled = true
```

**Recommended** (2 min):
```toml
[project]
name = "my-project"
root = "."
doc_root = "docs/"
excluded_dirs = [".git", "node_modules", "venv", "dist"]

[confidence]
auto_commit_threshold = 0.90
auto_stage_threshold = 0.80

[healers.fix_broken_links]
enabled = true
fuzzy_threshold = 0.80

[healers.detect_staleness]
enabled = true
staleness_threshold_days = 30

[git]
auto_commit = true
commit_prefix = "[docs]"
```

---

## Project Type Configs

| Project Type | excluded_dirs | fuzzy_threshold | staleness_days | duplicates | disclosure |
|--------------|---------------|-----------------|----------------|------------|------------|
| Python API | `.git`, `venv`, `__pycache__`, `dist`, `build` | 0.70 | 30 | Yes | No |
| React/Vue | `.git`, `node_modules`, `dist`, `build`, `storybook-static` | 0.85 | 60 | No | No |
| Rust CLI | `.git`, `target`, `node_modules` | 0.70 | 30 | Yes | Yes |
| Markdown Wiki | `.git` | 0.75 | 90 | Yes | Yes |
| Sphinx | `.git`, `venv`, `_build`, `_static`, `_templates` | 0.80 | 30 | Yes | No |
| MkDocs/Docusaurus | `.git`, `node_modules`, `build`, `.docusaurus` | 0.80 | 30 | No | No |

### Python API

```toml
[healers.detect_staleness]
deprecated_patterns = ['python2\s+', '\$\s+sudo\s+pip']

[healers.resolve_duplicates]
hierarchy_rules = ["README.md", "docs/reference/api.md", "docs/guides/", "docs/"]
```

### Rust CLI

```toml
[healers.enforce_disclosure.layers.overview]
max_lines = 50
file_patterns = ["README.md"]

[healers.enforce_disclosure.layers.reference]
max_lines = 500
file_patterns = ["docs/commands/*.md"]
```

### Markdown Wiki

```toml
[healers.balance_references]
enabled = true
backlink_format = "**See also**: [{title}]({path})"
```

---

## Configuration Recipes

| Mode | auto_commit_threshold | fuzzy_threshold | auto_commit | format |
|------|----------------------|-----------------|-------------|--------|
| Conservative | 0.95 | 0.90 | true | markdown |
| Aggressive | 0.80 | 0.70 | true | markdown |
| CI/CD | 1.0 | 0.80 | false | json |
| Pre-commit | 0.90 | 0.80 | false | markdown |
| Weekly batch | 1.0 | 0.80 | false | patch |

---

## Custom Healer (5 min)

```bash
cp templates/custom_healer_template.py guardian/healers/my_healer.py
```

```python
from guardian.core.base import HealingSystem, HealingReport, Change

class EnforceTerminology(HealingSystem):
    """Replace deprecated terms with approved alternatives."""

    def __init__(self, config):
        super().__init__(config)
        healer_config = config.get('healers', {}).get('enforce_terminology', {})
        self.rules = healer_config.get('rules', {})
        # {"master branch": "main branch", "whitelist": "allowlist"}

    def check(self) -> HealingReport:
        changes = []
        for doc_file in self.doc_root.rglob('*.md'):
            content = doc_file.read_text()
            for old_term, new_term in self.rules.items():
                if old_term.lower() in content.lower():
                    changes.append(Change(
                        file=doc_file, line=0,
                        old_content=old_term, new_content=new_term,
                        confidence=0.95,
                        reason=f"Replace '{old_term}' with '{new_term}'",
                        healer="enforce_terminology"
                    ))
        return self.create_report(mode="check", changes=changes, ...)

    def heal(self, min_confidence=None) -> HealingReport:
        # Standard pattern: check → filter by confidence → validate → apply
        ...
```

Config:
```toml
[healers.enforce_terminology]
enabled = true
rules = { "master branch" = "main branch", "whitelist" = "allowlist" }
```

---

## CI Integration

**GitHub Actions**:
```yaml
- name: Check docs
  run: python guardian/heal.py --config config.toml --check --strict
```

**GitLab CI**:
```yaml
script:
  - python guardian/heal.py --config config.toml --check --strict
only:
  changes: [docs/**/*]
```

**Pre-commit**:
```yaml
# .pre-commit-config.yaml
- id: doc-guardian
  entry: python guardian/heal.py --config config.toml --heal
  files: \.md$
```

**npm**:
```json
"scripts": {
  "docs:heal": "python guardian/heal.py --config config.toml --heal",
  "prebuild": "npm run docs:heal"
}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Too many false positives | Raise `auto_commit_threshold` to 0.95, `fuzzy_threshold` to 0.90 |
| Too many changes at once | Run `--only fix_broken_links` first, or `--min-confidence 0.95` |
| Healer not finding issues | Check `file_extensions`, verify not in `excluded_dirs` |
| Git conflicts | Run on clean working tree, or set `auto_commit = false` |
| Slow performance | Exclude large dirs, run `--only` specific healers |
| Custom healer not discovered | Must be in `guardian/healers/`, must inherit `HealingSystem`, must have matching config section |

---

## Related Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) - Core abstractions
- [CONFIG_GUIDE.md](CONFIG_GUIDE.md) - All config options
- [CUSTOM_HEALER_QUICKSTART.md](CUSTOM_HEALER_QUICKSTART.md) - Full healer guide
