"""
Confidence scoring model for healing operations.

Multi-factor confidence calculation determines action thresholds:
- auto_commit: High confidence (≥90%) - changes committed automatically
- auto_stage: Medium confidence (≥80%) - changes staged for review
- report_only: Low confidence (<80%) - changes reported only
"""

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class ConfidenceFactors:
    """
    Factors contributing to confidence score.

    All values should be 0.0-1.0 where 1.0 = highest confidence.

    Attributes:
        pattern_match: How well the detected pattern matches known patterns
                      1.0 = exact match, 0.5 = partial match, 0.0 = no match

        change_magnitude: Size/impact of the change (inverse scoring)
                         1.0 = small change (1-5 lines), 0.5 = medium (6-20 lines),
                         0.0 = large change (>50 lines)

        risk_assessment: Risk level of the change (inverse scoring)
                        1.0 = low risk (typo fix), 0.5 = medium risk (link change),
                        0.0 = high risk (structural change)

        historical_accuracy: Past success rate for this type of change
                            1.0 = 100% past success, 0.5 = 50% success, 0.0 = no history

    Weights:
        Default weights can be overridden in config:
        - pattern: 40% (most important - did we recognize the issue?)
        - magnitude: 30% (how big is the change?)
        - risk: 20% (how risky is this change?)
        - history: 10% (what's our track record?)
    """
    pattern_match: float
    change_magnitude: float
    risk_assessment: float
    historical_accuracy: float

    # Default weights (can be overridden via config)
    WEIGHTS = {
        'pattern': 0.40,
        'magnitude': 0.30,
        'risk': 0.20,
        'history': 0.10
    }

    def __post_init__(self):
        """Validate that all factors are in valid range."""
        for name in ['pattern_match', 'change_magnitude', 'risk_assessment', 'historical_accuracy']:
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")


def calculate_confidence(
    factors: ConfidenceFactors,
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Calculate overall confidence score using weighted factors.

    Formula:
        confidence = (pattern * w_p) + (magnitude * w_m) + (risk * w_r) + (history * w_h)

    Where w_x are the weights (default: 0.40, 0.30, 0.20, 0.10).

    Args:
        factors: ConfidenceFactors instance with all scores
        weights: Optional weight overrides (must sum to 1.0)

    Returns:
        Confidence score between 0.0 and 1.0

    Example:
        >>> factors = ConfidenceFactors(
        ...     pattern_match=0.95,      # Strong pattern match
        ...     change_magnitude=0.90,   # Small change
        ...     risk_assessment=0.85,    # Low risk
        ...     historical_accuracy=0.92 # High success rate
        ... )
        >>> calculate_confidence(factors)
        0.908
    """
    w = weights or ConfidenceFactors.WEIGHTS

    # Validate weights sum to 1.0 (with floating point tolerance)
    if weights:
        total = sum(w.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total}")

    score = (
        factors.pattern_match * w['pattern'] +
        factors.change_magnitude * w['magnitude'] +
        factors.risk_assessment * w['risk'] +
        factors.historical_accuracy * w['history']
    )

    # Clamp to valid range (handle floating point errors)
    return max(0.0, min(1.0, score))


def get_action_threshold(confidence: float, config: Dict) -> str:
    """
    Determine action based on confidence and thresholds.

    Thresholds are read from config (with defaults):
    - auto_commit_threshold: 0.90 (90%)
    - auto_stage_threshold: 0.80 (80%)

    Args:
        confidence: Confidence score (0.0-1.0)
        config: Configuration dict. Optional keys:
                - confidence.auto_commit_threshold (default: 0.90)
                - confidence.auto_stage_threshold (default: 0.80)

    Returns:
        "auto_commit" - Changes committed automatically (high confidence)
        "auto_stage" - Changes staged for review (medium confidence)
        "report_only" - Changes reported only (low confidence)

    Example:
        >>> config = {
        ...     'confidence': {
        ...         'auto_commit_threshold': 0.90,
        ...         'auto_stage_threshold': 0.80
        ...     }
        ... }
        >>> get_action_threshold(0.95, config)
        'auto_commit'
        >>> get_action_threshold(0.85, config)
        'auto_stage'
        >>> get_action_threshold(0.75, config)
        'report_only'
    """
    confidence_config = config.get('confidence', {})
    auto_commit = confidence_config.get('auto_commit_threshold', 0.90)
    auto_stage = confidence_config.get('auto_stage_threshold', 0.80)

    if confidence >= auto_commit:
        return "auto_commit"
    elif confidence >= auto_stage:
        return "auto_stage"
    else:
        return "report_only"


def assess_change_magnitude(old_content: str, new_content: str) -> float:
    """
    Assess magnitude of change (smaller = higher score).

    Scoring rules:
    - 1-5 lines changed: 1.0
    - 6-10 lines: 0.9
    - 11-20 lines: 0.8
    - 21-50 lines: 0.6
    - 51-100 lines: 0.4
    - >100 lines: 0.2

    Args:
        old_content: Original content
        new_content: Modified content

    Returns:
        Magnitude score (0.0-1.0, higher = smaller change)
    """
    old_lines = old_content.count('\n') + 1 if old_content else 0
    new_lines = new_content.count('\n') + 1 if new_content else 0
    diff_lines = abs(new_lines - old_lines)

    if diff_lines <= 5:
        return 1.0
    elif diff_lines <= 10:
        return 0.9
    elif diff_lines <= 20:
        return 0.8
    elif diff_lines <= 50:
        return 0.6
    elif diff_lines <= 100:
        return 0.4
    else:
        return 0.2


def assess_risk_level(change_type: str) -> float:
    """
    Assess risk level based on change type (lower risk = higher score).

    Risk levels:
    - typo_fix: 1.0 (very safe)
    - broken_link_fix: 0.9 (safe if target exists)
    - formatting_fix: 0.85 (usually safe)
    - sync_canonical: 0.8 (template-driven)
    - structural_change: 0.5 (medium risk)
    - code_change: 0.3 (higher risk)
    - unknown: 0.5 (default medium)

    Args:
        change_type: String identifier of change type

    Returns:
        Risk score (0.0-1.0, higher = lower risk)
    """
    risk_map = {
        'typo_fix': 1.0,
        'broken_link_fix': 0.9,
        'formatting_fix': 0.85,
        'sync_canonical': 0.8,
        'structural_change': 0.5,
        'code_change': 0.3,
    }

    return risk_map.get(change_type, 0.5)  # Default to medium risk
