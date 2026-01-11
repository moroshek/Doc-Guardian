# Confidence Model

Score 0.0-1.0 determines action: auto-commit, stage, or report-only.

## Formula

```python
confidence = (
    pattern_match * 0.40 +      # How well issue matches known patterns
    change_magnitude * 0.30 +   # Smaller = higher (1-5 lines = 1.0, >100 = 0.2)
    risk_assessment * 0.20 +    # Change type risk (typo=1.0, structural=0.5, code=0.3)
    historical_accuracy * 0.10  # Past success rate for this healer
)
```

## Magnitude Scoring

| Lines Changed | Score |
|---------------|-------|
| 1-5 | 1.0 |
| 6-10 | 0.9 |
| 11-20 | 0.8 |
| 21-50 | 0.6 |
| 51-100 | 0.4 |
| >100 | 0.2 |

## Risk Levels

| Change Type | Score |
|-------------|-------|
| Typo fix | 1.0 |
| Broken link fix | 0.9 |
| Formatting fix | 0.85 |
| Sync canonical | 0.8 |
| Structural change | 0.5 |
| Code change | 0.3 |

## Action Thresholds

| Score | Action |
|-------|--------|
| >= 0.90 | auto_commit |
| >= 0.80 | auto_stage |
| < 0.80 | report_only |

## Configuration

```toml
[confidence]
# Adjust thresholds per project risk tolerance
auto_commit_threshold = 0.90  # Production docs: 0.95, Personal: 0.85
auto_stage_threshold = 0.80   # Production docs: 0.90, Personal: 0.75

# Custom weights (optional)
# pattern_weight = 0.40
# magnitude_weight = 0.30
# risk_weight = 0.20
# history_weight = 0.10
```

## Debugging Low Confidence

```bash
python guardian/heal.py --config config.toml --heal --verbose
```

Output shows factor breakdown:
```
[BrokenLinkHealer] Confidence breakdown:
  Pattern match:       0.50  (partial match)
  Change magnitude:    0.60  (30 lines)
  Risk assessment:     0.90  (link fix)
  Historical accuracy: 0.50  (no history)
  -> Overall: 0.60 (report_only)
```

## Common Fixes

| Problem | Solution |
|---------|----------|
| Low pattern match (<0.7) | Add specific patterns to healer |
| Low magnitude (<0.7) | Break large changes into smaller chunks |
| No history (=0.5) | Run on test cases to build history |
| Changes not auto-committing | Lower threshold or improve confidence factors |

---

**Last Updated**: 2026-01-11
