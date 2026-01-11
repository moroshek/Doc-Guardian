# EnforceDisclosureHealer Usage Guide

## Overview

The `EnforceDisclosureHealer` prevents detail creep by enforcing progressive disclosure rules across documentation layers.

## Configuration

Add to your `config.json`:

```json
{
  "healers": {
    "enforce_disclosure": {
      "layer_definitions": {
        "overview": {
          "max_lines": 50,
          "allowed_depth": 2,
          "files": ["README.md", "CLAUDE.md", "*/index.md"]
        },
        "guide": {
          "max_lines": 200,
          "allowed_depth": 3,
          "files": ["docs/guides/*.md"]
        },
        "reference": {
          "max_lines": 1000,
          "allowed_depth": 5,
          "files": ["docs/reference/*.md", "docs/api/*.md"]
        }
      },
      "jargon_patterns": [
        "memgraph",
        "embeddings",
        "vector database",
        "reranker",
        "tensor",
        "transformer"
      ],
      "detail_indicators": [
        {
          "pattern": "```(?:python|bash|sql).{200,}```",
          "description": "Long code examples"
        },
        {
          "pattern": "(?:Step \\d+:|1\\.|2\\.|3\\.).{100,}",
          "description": "Detailed step-by-step instructions"
        },
        {
          "pattern": "(?:Parameter|Argument|Flag):\\s+",
          "description": "API/CLI documentation"
        }
      ],
      "keyword_mappings": {
        "search": "docs/domains/search.md",
        "rag": "docs/domains/search.md",
        "deploy": "docs/deployment.md",
        "docker": "docs/deployment.md",
        "frontend": "docs/frontend.md",
        "backend": "docs/backend.md"
      }
    }
  }
}
```

## Usage

### Python API

```python
from guardian.healers.enforce_disclosure import EnforceDisclosureHealer

# Load your config
config = load_config('config.json')

# Initialize healer
healer = EnforceDisclosureHealer(config)

# Check for violations
report = healer.check()
print(f"Found {report.issues_found} violations")

for change in report.changes:
    print(f"- {change.reason} (confidence: {change.confidence:.0%})")

# Apply fixes above 80% confidence
heal_report = healer.heal(min_confidence=0.80)
print(f"Fixed {heal_report.issues_fixed} issues")
```

### CLI Usage

```bash
# Check only (dry run)
python -m guardian.cli heal --healer enforce_disclosure --check

# Apply fixes above 80% confidence
python -m guardian.cli heal --healer enforce_disclosure --min-confidence 0.80

# Apply all fixes (use with caution!)
python -m guardian.cli heal --healer enforce_disclosure --min-confidence 0.60
```

## Violation Types

### 1. Oversized Sections

**Detected when**: Section line count exceeds layer's `max_lines`

**Example**:
```markdown
# README.md (overview layer, max 50 lines)

## Installation  <!-- 80 lines - VIOLATION -->
...
```

**Confidence**: 85% if target file is known, 65% otherwise

**Fix**: Moves section to appropriate detail layer, replaces with link

---

### 2. Depth Violations

**Detected when**: Heading level exceeds layer's `allowed_depth`

**Example**:
```markdown
# README.md (overview layer, max depth 2)

## Features
### Core Features
#### Database  <!-- Level 4 - VIOLATION -->
```

**Confidence**: 75% if target known, 60% otherwise

**Fix**: Suggests moving deeply nested content to reference layer

---

### 3. Jargon in Overview

**Detected when**: Technical terms appear in quick start/overview sections

**Example**:
```markdown
# Quick Start

Install Memgraph and configure the vector database...
<!-- "Memgraph" and "vector database" are jargon - VIOLATION -->
```

**Confidence**: 65% (manual review recommended)

**Fix**: Flags for manual review (no automatic replacement)

---

### 4. Detail Creep

**Detected when**: Detail indicators (long code, step-by-step, API docs) appear in overview

**Example**:
```markdown
# README.md

## Usage

Step 1: Clone the repository
Step 2: Install dependencies with pip install -r requirements.txt
Step 3: Configure the database connection string in config.yaml
Step 4: Run the migration script...
<!-- Long step-by-step - VIOLATION -->
```

**Confidence**: 70% if target known, 60% otherwise

**Fix**: Moves to guide layer, replaces with link

---

## Confidence Scoring

| Confidence | Meaning | Action |
|------------|---------|--------|
| 85% | Clear violation, known target | Auto-apply |
| 75% | Likely violation, probable target | Auto-apply (threshold 0.75) |
| 65-70% | Violation detected, unclear target | Report only (threshold 0.80) |
| <65% | Ambiguous case | Manual review required |

## Layer Definitions

Customize layers to match your project structure:

```python
layer_definitions = {
    "overview": {
        "max_lines": 50,        # Keep it short
        "allowed_depth": 2,     # Max ## headings
        "files": ["README.md", "CLAUDE.md"]
    },
    "guide": {
        "max_lines": 200,       # More detail allowed
        "allowed_depth": 3,     # Max ### headings
        "files": ["docs/guides/*.md"]
    },
    "reference": {
        "max_lines": 1000,      # Full detail
        "allowed_depth": 5,     # Deep nesting OK
        "files": ["docs/reference/*.md", "docs/api/*.md"]
    }
}
```

## Keyword Mappings

Map section title keywords to target files:

```python
keyword_mappings = {
    "search": "docs/domains/search.md",
    "rag": "docs/domains/search.md",
    "memgraph": "docs/domains/database.md",
    "deploy": "docs/deployment.md",
    "docker": "docs/deployment.md",
    "frontend": "docs/frontend.md",
    "backend": "docs/backend.md",
    "api": "docs/api/reference.md"
}
```

When a section title contains a keyword, the healer suggests that target file.

## Examples

### Before Healing

```markdown
# README.md

## Search Pipeline (120 lines)

The search pipeline uses Memgraph vector database with Voyage AI embeddings...

Step 1: Configure the search parameters in config.yaml
Step 2: Initialize the vector database connection
Step 3: Run the embedding generation script...
<!-- 120 lines of detail -->
```

**Violations**:
- Oversized section (120 > 50 lines)
- Jargon ("Memgraph", "vector database", "embeddings")
- Detail creep (step-by-step instructions)

### After Healing

```markdown
# README.md

## Search Pipeline

See [search.md](docs/domains/search.md) for full documentation.
```

```markdown
# docs/domains/search.md

## Search Pipeline

The search pipeline uses Memgraph vector database with Voyage AI embeddings...

Step 1: Configure the search parameters in config.yaml
Step 2: Initialize the vector database connection
Step 3: Run the embedding generation script...
<!-- Full 120 lines moved here -->
```

## Best Practices

1. **Start conservative**: Use `min_confidence=0.85` for first run
2. **Review changes**: Check git diff before committing
3. **Tune thresholds**: Adjust `max_lines` and `allowed_depth` for your project
4. **Add keywords**: Update `keyword_mappings` as your docs grow
5. **Iterate**: Run after major doc updates to catch creep early

## Troubleshooting

### Issue: Too many false positives

**Solution**: Increase `max_lines` for affected layers

```json
"overview": {
  "max_lines": 75  // was 50
}
```

### Issue: Not detecting violations

**Solution**: Check file patterns match your structure

```json
"files": ["*.md", "docs/**/*.md"]  // Use glob patterns
```

### Issue: Wrong target file suggestions

**Solution**: Add more keyword mappings

```json
"keyword_mappings": {
  "custom_keyword": "docs/custom_target.md"
}
```

## Integration with Other Healers

`EnforceDisclosureHealer` works well with:

- **FixBrokenLinksHealer**: Fixes links after sections move
- **ResolveDuplicatesHealer**: Detects duplicate content across layers
- **DetectStalenessHealer**: Flags outdated content in wrong layers

Run healers in sequence:

```bash
python -m guardian.cli heal --healer enforce_disclosure
python -m guardian.cli heal --healer fix_broken_links
python -m guardian.cli heal --healer resolve_duplicates
```
