"""
Guardian Core - Universal base framework for documentation healing systems.

This package provides config-driven abstractions extracted from TCF's healing patterns.
All classes are project-agnostic and depend only on Python stdlib.
"""

from .base import Change, HealingReport, HealingSystem
from .confidence import (
    ConfidenceFactors,
    calculate_confidence,
    get_action_threshold,
    assess_change_magnitude,
    assess_risk_level
)
from .validation import (
    validate_syntax,
    validate_links,
    validate_change,
    validate_all_changes
)
from .git_utils import (
    rollback_file,
    git_add,
    git_commit,
    git_status_clean,
    git_diff,
    is_git_repo
)
from .reporting import (
    generate_markdown_report,
    generate_json_report,
    generate_console_output,
    save_report
)
from .file_cache import (
    FileCache,
    get_file_cache,
    reset_global_cache,
    content_hash,
    simhash,
    hamming_distance,
    are_similar
)
from .config_validator import (
    ConfigError,
    ValidationResult,
    validate_config_schema,
    validate_path_traversal,
    validate_path_exists,
    validate_threshold,
    validate_regex_pattern,
    ensure_list,
    safe_read_file,
    validate_and_load_config
)

__all__ = [
    # Base classes
    'Change',
    'HealingReport',
    'HealingSystem',

    # Confidence
    'ConfidenceFactors',
    'calculate_confidence',
    'get_action_threshold',
    'assess_change_magnitude',
    'assess_risk_level',

    # Validation
    'validate_syntax',
    'validate_links',
    'validate_change',
    'validate_all_changes',

    # Git
    'rollback_file',
    'git_add',
    'git_commit',
    'git_status_clean',
    'git_diff',
    'is_git_repo',

    # Reporting
    'generate_markdown_report',
    'generate_json_report',
    'generate_console_output',
    'save_report',

    # File Cache
    'FileCache',
    'get_file_cache',
    'reset_global_cache',
    'content_hash',
    'simhash',
    'hamming_distance',
    'are_similar',

    # Config Validation
    'ConfigError',
    'ValidationResult',
    'validate_config_schema',
    'validate_path_traversal',
    'validate_path_exists',
    'validate_threshold',
    'validate_regex_pattern',
    'ensure_list',
    'safe_read_file',
    'validate_and_load_config',
]

__version__ = '0.1.0'
