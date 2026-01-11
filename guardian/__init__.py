"""
Doc Guardian - Self-healing documentation for every project.

A confidence-based documentation maintenance system that automatically
detects and repairs common documentation issues.
"""

from guardian.core import (
    Change,
    HealingReport,
    HealingSystem,
    ConfidenceFactors,
    calculate_confidence,
    get_action_threshold,
)

__version__ = "0.1.0"
__author__ = "Anthropic, PBC"
__license__ = "MIT"

__all__ = [
    # Core classes
    "Change",
    "HealingReport",
    "HealingSystem",
    # Confidence
    "ConfidenceFactors",
    "calculate_confidence",
    "get_action_threshold",
    # Version info
    "__version__",
    "__author__",
    "__license__",
]
