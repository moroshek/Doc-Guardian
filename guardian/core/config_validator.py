"""
Configuration Validator for Doc Guardian.

Comprehensive validation layer that prevents ALL config-related crashes and security issues.

FIXED ISSUES (from CONFIG_VALIDATION_AUDIT.md):
1. Path traversal prevention - Validates paths stay within project root
2. Numeric range validation - Confidence 0.0-1.0, thresholds positive
3. Type checking at load time - Validates types before any healer runs
4. Resource limits - Caps pattern counts, regex complexity
5. List vs string coercion - Proper handling of string→list conversion
6. Path existence validation - Validates paths exist before use
7. Regex validation - Tests compile before use, ReDoS prevention
8. Clear error messages - Actionable errors with context

This module MUST be called before any healing operations via:
    validator = ConfigValidator(project_root)
    result = validator.validate(config)
    if not result.is_valid:
        raise ConfigValidationError(result.errors)
"""

import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# RESOURCE LIMITS (Issue 4)
# =============================================================================
MAX_PATTERNS = 1000          # Max patterns in any list (timestamp_patterns, etc.)
MAX_PATTERN_LENGTH = 10000   # Max length of a single regex pattern
MAX_PATH_LENGTH = 4096       # Max path length (Linux PATH_MAX)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB max config file size
MAX_ARRAY_SIZE = 10000       # Max items in any array
MAX_NESTING_DEPTH = 20       # Max config nesting depth
MAX_STRING_LENGTH = 100000   # Max string value length (100KB)

# =============================================================================
# ReDoS PREVENTION PATTERNS (Issue 7)
# =============================================================================
DANGEROUS_REGEX_PATTERNS = [
    r'\(\.\*\?\)\{',     # (.*?){n} - catastrophic backtracking
    r'\(\[.*\]\+\)\+',   # ([...]+)+ - nested quantifiers
    r'\(\.\+\)\+',       # (.+)+ - nested quantifiers
    r'\(\.\*\)\+',       # (.*)+ - nested quantifiers
    r'\(\.\+\)\*',       # (.+)* - nested quantifiers
    r'\(\.\*\)\*',       # (.*)* - nested quantifiers
    r'\([\w\W]+\+\)\+',  # (\w+)+ - nested word quantifiers
    r'(?:\.\+){2,}',     # .+.+.+ - multiple consecutive quantifiers
]


class ConfigError(Exception):
    """Configuration validation error with context (Issue 8)."""

    def __init__(self, key: str, message: str, value: Any = None, suggestion: str = None):
        self.key = key
        self.value = value
        self.suggestion = suggestion
        full_message = f"Config error at '{key}': {message}"
        if value is not None:
            full_message += f" (got: {value!r})"
        if suggestion:
            full_message += f". Suggestion: {suggestion}"
        super().__init__(full_message)


class ConfigValidationError(Exception):
    """
    Raised when configuration validation fails with multiple errors.

    Use this exception when aggregating validation errors.
    """

    def __init__(self, errors: List[str], warnings: List[str] = None):
        self.errors = errors
        self.warnings = warnings or []
        message = f"Configuration validation failed with {len(errors)} error(s):\n"
        message += "\n".join(f"  - {err}" for err in errors[:20])  # Show first 20
        if len(errors) > 20:
            message += f"\n  ... and {len(errors) - 20} more errors"
        super().__init__(message)


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_config: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.is_valid

    def raise_if_invalid(self) -> 'ValidationResult':
        """Raise ConfigValidationError if validation failed."""
        if not self.is_valid:
            raise ConfigValidationError(self.errors, self.warnings)
        return self

    def log_warnings(self) -> 'ValidationResult':
        """Log any warnings."""
        for warning in self.warnings:
            logger.warning(f"Config warning: {warning}")
        return self


def validate_path_traversal(
    path: Union[str, Path],
    allowed_root: Union[str, Path],
    key_name: str = "path"
) -> Path:
    """
    Validate that a path doesn't escape the allowed root directory (Issue 1).

    Security checks:
    - No '..' components that escape root
    - No symlinks pointing outside root
    - Path length limits
    - No null bytes or newlines
    - Resolves ~/ to home directory

    Args:
        path: Path to validate
        allowed_root: Directory that path must be within
        key_name: Config key name for error messages

    Returns:
        Resolved absolute path

    Raises:
        ConfigError: If path escapes allowed root or has security issues
    """
    path_str = str(path)
    root_str = str(allowed_root)

    # Check for null bytes (security issue)
    if '\x00' in path_str:
        raise ConfigError(
            key_name,
            "Path contains null byte (security violation)",
            path_str,
            "Remove null characters from path"
        )

    # Check for newlines (malformed config)
    if '\n' in path_str or '\r' in path_str:
        raise ConfigError(
            key_name,
            "Path contains newline characters (malformed config)",
            path_str,
            "Remove newline characters from path"
        )

    # Check path length
    if len(path_str) > MAX_PATH_LENGTH:
        raise ConfigError(
            key_name,
            f"Path exceeds maximum length of {MAX_PATH_LENGTH} characters",
            f"...{path_str[-50:]}",
            "Use a shorter path"
        )

    # Expand ~ to home directory
    if path_str.startswith('~'):
        path_str = os.path.expanduser(path_str)
        logger.debug(f"Expanded ~ in '{key_name}' to: {path_str}")

    try:
        # Convert to Path objects
        path_obj = Path(path_str)
        root_obj = Path(root_str)

        # Resolve to absolute paths
        if path_obj.is_absolute():
            resolved = path_obj.resolve()
        else:
            resolved = (root_obj / path_obj).resolve()

        root_resolved = root_obj.resolve()

        # Check containment using relative_to (safer than string prefix)
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            raise ConfigError(
                key_name,
                f"Path escapes project root '{root_resolved}'",
                str(path),
                f"Use a path within '{root_resolved}'"
            )

        # Check for '..' in original path (explicit traversal attempt)
        if '..' in str(path):
            raise ConfigError(
                key_name,
                "Path contains '..' (directory traversal not allowed)",
                str(path),
                "Use an absolute path or path without '..' components"
            )

        return resolved

    except ConfigError:
        raise
    except Exception as e:
        raise ConfigError(key_name, f"Invalid path: {e}", str(path))


def validate_path_exists(
    path: Path,
    key_name: str = "path",
    must_be_dir: bool = False,
    must_be_file: bool = False
) -> Path:
    """
    Validate that a path exists and meets requirements.

    Args:
        path: Path to validate
        key_name: Config key name for error messages
        must_be_dir: If True, path must be a directory
        must_be_file: If True, path must be a file

    Returns:
        Resolved path

    Raises:
        ConfigError: If path doesn't exist or doesn't meet requirements
    """
    # Expand ~ to home directory
    expanded = Path(str(path).replace('~', str(Path.home())))

    if not expanded.exists():
        raise ConfigError(
            key_name,
            f"Path does not exist: {path}",
            str(path)
        )

    if must_be_dir and not expanded.is_dir():
        raise ConfigError(
            key_name,
            f"Path must be a directory: {path}",
            str(path)
        )

    if must_be_file and not expanded.is_file():
        raise ConfigError(
            key_name,
            f"Path must be a file: {path}",
            str(path)
        )

    return expanded.resolve()


def validate_threshold(
    value: Any,
    key_name: str,
    min_val: float = 0.0,
    max_val: float = 1.0
) -> float:
    """
    Validate a numeric threshold is within range (Issue 2).

    Args:
        value: Value to validate
        key_name: Config key name for error messages
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated float value

    Raises:
        ConfigError: If value is invalid or out of range
    """
    if value is None:
        raise ConfigError(
            key_name,
            "Value is null/None",
            None,
            f"Set to a number between {min_val} and {max_val}"
        )

    # Check for string that should be a number (common YAML/TOML issue)
    if isinstance(value, str):
        raise ConfigError(
            key_name,
            f"Must be a number, got string",
            value,
            f"Remove quotes: use {key_name.split('.')[-1]} = 0.9 instead of \"{value}\""
        )

    if not isinstance(value, (int, float)):
        raise ConfigError(
            key_name,
            f"Must be numeric, got {type(value).__name__}",
            value,
            f"Use a number like 0.9"
        )

    # Check for special float values
    if isinstance(value, float):
        if value != value:  # NaN check
            raise ConfigError(
                key_name,
                "Value is NaN (Not a Number)",
                "NaN",
                f"Use a valid number between {min_val} and {max_val}"
            )
        if value == float('inf') or value == float('-inf'):
            raise ConfigError(
                key_name,
                "Value is infinite",
                "Infinity",
                f"Use a finite number between {min_val} and {max_val}"
            )

    if value < min_val:
        raise ConfigError(
            key_name,
            f"Value too low (minimum is {min_val})",
            value,
            f"Increase to at least {min_val}"
        )

    if value > max_val:
        raise ConfigError(
            key_name,
            f"Value too high (maximum is {max_val})",
            value,
            f"Decrease to at most {max_val}"
        )

    return float(value)


def validate_positive_int(value: Any, key_name: str) -> int:
    """
    Validate a positive integer.

    Args:
        value: Value to validate
        key_name: Config key name for error messages

    Returns:
        Validated integer

    Raises:
        ConfigError: If value is invalid or negative
    """
    if value is None:
        raise ConfigError(key_name, "Value cannot be None")

    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(
            key_name,
            f"Must be an integer, got {type(value).__name__}",
            value
        )

    if value < 0:
        raise ConfigError(
            key_name,
            "Must be non-negative",
            value
        )

    return value


def ensure_list(value: Any, key_name: str, coerce_string: bool = True) -> List[Any]:
    """
    Ensure value is a list, optionally converting string to single-item list (Issue 5).

    IMPORTANT: If a string is passed where a list is expected, it will be iterated
    character by character in Python, causing bugs. This function prevents that.

    Args:
        value: Value to convert
        key_name: Config key name for error messages
        coerce_string: If True, convert single string to [string]. If False, raise error.

    Returns:
        List value

    Raises:
        ConfigError: If value cannot be converted to list
    """
    if value is None:
        logger.debug(f"Config '{key_name}' is None, using empty list")
        return []

    if isinstance(value, str):
        if coerce_string:
            logger.warning(
                f"Config '{key_name}': Expected list but got string '{value}'. "
                f"Converting to single-item list. Use [{key_name.split('.')[-1]} = [\"{value}\"]] in config."
            )
            return [value]
        else:
            raise ConfigError(
                key_name,
                "Expected a list, got a string",
                value,
                f"Use [\"{value}\"] for a single-item list, or [] for empty"
            )

    if isinstance(value, list):
        # Validate list size
        if len(value) > MAX_ARRAY_SIZE:
            raise ConfigError(
                key_name,
                f"List has {len(value)} items, exceeds limit of {MAX_ARRAY_SIZE}",
                f"[{len(value)} items]",
                f"Reduce to fewer than {MAX_ARRAY_SIZE} items"
            )
        return value

    if isinstance(value, dict):
        raise ConfigError(
            key_name,
            f"Expected list, got dict/object",
            value,
            "Use list syntax: [item1, item2] or YAML list with - prefix"
        )

    raise ConfigError(
        key_name,
        f"Expected list, got {type(value).__name__}",
        value,
        "Use list syntax: [item1, item2]"
    )


def validate_regex_pattern(
    pattern: Any,
    key_name: str,
    check_redos: bool = True
) -> re.Pattern:
    """
    Validate and compile a regex pattern (Issue 7).

    Checks for:
    - Correct type (string)
    - Length limits
    - Valid regex syntax
    - ReDoS vulnerabilities (catastrophic backtracking)

    Args:
        pattern: Regex pattern string
        key_name: Config key name for error messages
        check_redos: If True, check for ReDoS vulnerabilities

    Returns:
        Compiled regex pattern

    Raises:
        ConfigError: If pattern is invalid or potentially dangerous
    """
    if pattern is None:
        raise ConfigError(
            key_name,
            "Pattern is null/None",
            None,
            "Provide a valid regex pattern string"
        )

    if not isinstance(pattern, str):
        raise ConfigError(
            key_name,
            f"Pattern must be a string, got {type(pattern).__name__}",
            pattern,
            "Enclose pattern in quotes"
        )

    if len(pattern) == 0:
        raise ConfigError(
            key_name,
            "Pattern is empty",
            "",
            "Provide a non-empty regex pattern"
        )

    if len(pattern) > MAX_PATTERN_LENGTH:
        raise ConfigError(
            key_name,
            f"Pattern exceeds maximum length of {MAX_PATTERN_LENGTH} characters",
            f"...{pattern[-50:]}",
            "Use a shorter pattern or split into multiple patterns"
        )

    # Check for ReDoS patterns (catastrophic backtracking)
    if check_redos:
        for dangerous_pattern in DANGEROUS_REGEX_PATTERNS:
            if re.search(dangerous_pattern, pattern):
                raise ConfigError(
                    key_name,
                    "Pattern may cause catastrophic backtracking (ReDoS vulnerability)",
                    pattern,
                    "Simplify the pattern: avoid nested quantifiers like (.*)+, (.+)+, or (a+)+"
                )

    # Try to compile
    try:
        return re.compile(pattern)
    except re.error as e:
        # Provide detailed error message based on the error
        error_msg = str(e)
        position_info = ""

        if hasattr(e, 'pos') and e.pos is not None:
            position_info = f" at position {e.pos}"

        # Common error suggestions
        suggestions = {
            "unterminated": "Add the closing character (], ), etc.)",
            "missing )": "Add the missing closing parenthesis",
            "unbalanced": "Check that all brackets and parentheses are matched",
            "nothing to repeat": "Quantifier (*, +, ?) needs something before it",
            "bad escape": "Use double backslash \\\\ or raw string r'pattern'",
        }

        suggestion = "Check regex syntax"
        for key, sugg in suggestions.items():
            if key in error_msg.lower():
                suggestion = sugg
                break

        raise ConfigError(
            key_name,
            f"Invalid regex pattern{position_info}: {error_msg}",
            pattern,
            suggestion
        )


def validate_config_schema(
    config: Dict[str, Any],
    project_root: Optional[Path] = None,
    check_paths: bool = True
) -> ValidationResult:
    """
    Validate entire configuration against schema.

    Comprehensively validates all config sections addressing all 8 CRITICAL issues:
    1. Path traversal prevention
    2. Numeric range validation
    3. Type checking
    4. Resource limits
    5. List vs string coercion
    6. Path existence
    7. Regex validation
    8. Clear error messages

    Args:
        config: Full configuration dictionary
        project_root: Project root for path validation (defaults to cwd)
        check_paths: If True, verify paths exist (set False for tests)

    Returns:
        ValidationResult with errors and warnings
    """
    errors: List[str] = []
    warnings: List[str] = []
    validated_config: Dict[str, Any] = {}

    # Determine project root
    if project_root is None:
        project_root = Path.cwd()

    # Helper to add error with clear context
    def add_error(key: str, msg: str, suggestion: str = None):
        full_msg = f"[{key}] {msg}"
        if suggestion:
            full_msg += f" | Suggestion: {suggestion}"
        errors.append(full_msg)

    def add_warning(key: str, msg: str):
        warnings.append(f"[{key}] {msg}")

    # =========================================================================
    # Pre-flight checks
    # =========================================================================

    # Check config is not None (Issue 3)
    if config is None:
        add_error('config', 'Configuration is None (file may be empty)', 'Provide a valid config file')
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Check config is a dict (Issue 3)
    if not isinstance(config, dict):
        add_error('config', f'Configuration must be a dictionary, got {type(config).__name__}',
                 'Use TOML sections like [project] or YAML mappings')
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Check nesting depth (Issue 4 - Resource limits)
    def check_depth(obj: Any, path: str, depth: int) -> bool:
        if depth > MAX_NESTING_DEPTH:
            add_error(path, f'Config nesting too deep (max {MAX_NESTING_DEPTH})', 'Flatten config structure')
            return False
        if isinstance(obj, dict):
            for k, v in list(obj.items())[:100]:
                if not check_depth(v, f'{path}.{k}', depth + 1):
                    return False
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:100]):
                if not check_depth(v, f'{path}[{i}]', depth + 1):
                    return False
        return True

    if not check_depth(config, 'config', 0):
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # =========================================================================
    # [project] section - REQUIRED
    # =========================================================================
    project = config.get('project', {})

    if not project:
        add_error('project', 'Missing required [project] section',
                 'Add [project] section with root and doc_root keys')
    elif not isinstance(project, dict):
        add_error('project', f'Must be a section/dict, got {type(project).__name__}',
                 'Use [project] in TOML or project: in YAML')
    else:
        # Required: root (Issue 1, 6 - Path validation)
        if 'root' not in project:
            add_error('project.root', 'Required key missing',
                     'Add root = "." for current directory or absolute path')
        else:
            root_val = project['root']
            # Type check (Issue 3)
            if not isinstance(root_val, (str, Path)):
                add_error('project.root', f'Must be a string, got {type(root_val).__name__}',
                         'Use root = "path/to/project"')
            else:
                root_path = Path(root_val)
                # Expand ~ (Issue 5 in PH tests)
                if str(root_val).startswith('~'):
                    root_path = Path(os.path.expanduser(str(root_val)))
                    add_warning('project.root', f'Expanded ~ to {root_path}')

                if check_paths and not root_path.exists():
                    add_error('project.root', f"Path does not exist: {root_val}",
                             'Create the directory or use an existing path')
                else:
                    # Update project_root for later validations
                    project_root = root_path.resolve() if root_path.exists() else project_root

        # Required: doc_root (Issue 1 - Path traversal)
        if 'doc_root' not in project:
            add_error('project.doc_root', 'Required key missing',
                     'Add doc_root = "docs/" or similar')
        elif 'root' in project:
            doc_root_val = project['doc_root']
            # Type check (Issue 3)
            if not isinstance(doc_root_val, (str, Path)):
                add_error('project.doc_root', f'Must be a string, got {type(doc_root_val).__name__}',
                         'Use doc_root = "docs/"')
            else:
                try:
                    doc_root = Path(doc_root_val)
                    root_path = Path(project['root'])
                    if str(project['root']).startswith('~'):
                        root_path = Path(os.path.expanduser(project['root']))

                    # Path traversal check (Issue 1)
                    if check_paths and root_path.exists():
                        validate_path_traversal(doc_root, root_path, 'project.doc_root')

                    # Check for explicit traversal attempt
                    if '..' in str(doc_root_val):
                        add_error('project.doc_root', "Path contains '..' (directory traversal not allowed)",
                                 'Use a path within project root without ..')

                except ConfigError as e:
                    add_error('project.doc_root', str(e))

        # Optional: excluded_dirs (Issue 5 - List vs string)
        if 'excluded_dirs' in project:
            try:
                dirs = ensure_list(project['excluded_dirs'], 'project.excluded_dirs')
                # Check for None in list
                for i, d in enumerate(dirs):
                    if d is None:
                        add_error(f'project.excluded_dirs[{i}]', 'Contains None value',
                                 'Remove null entries from list')
                    elif not isinstance(d, str):
                        add_error(f'project.excluded_dirs[{i}]', f'Must be string, got {type(d).__name__}',
                                 'Use string values in list')
            except ConfigError as e:
                add_error('project.excluded_dirs', str(e))

    # =========================================================================
    # [confidence] section - OPTIONAL but validated if present (Issue 2)
    # =========================================================================
    confidence = config.get('confidence', {})

    if confidence and not isinstance(confidence, dict):
        add_error('confidence', f'Must be a section/dict, got {type(confidence).__name__}',
                 'Use [confidence] in TOML or confidence: in YAML')
    elif isinstance(confidence, dict):
        # Validate all threshold keys (Issue 2 - Numeric ranges)
        for threshold_key in ['auto_commit_threshold', 'auto_stage_threshold', 'report_only_threshold']:
            if threshold_key in confidence:
                try:
                    validate_threshold(
                        confidence[threshold_key],
                        f'confidence.{threshold_key}'
                    )
                except ConfigError as e:
                    add_error(f'confidence.{threshold_key}', str(e))

        # Check threshold ordering logic (commit > stage > report)
        commit_t = confidence.get('auto_commit_threshold')
        stage_t = confidence.get('auto_stage_threshold')
        report_t = confidence.get('report_only_threshold')

        if commit_t is not None and stage_t is not None:
            if isinstance(commit_t, (int, float)) and isinstance(stage_t, (int, float)):
                if commit_t < stage_t:
                    add_warning(
                        'confidence',
                        f'auto_commit_threshold ({commit_t}) < auto_stage_threshold ({stage_t}). '
                        'High-confidence changes will only be staged, not committed.'
                    )

        if stage_t is not None and report_t is not None:
            if isinstance(stage_t, (int, float)) and isinstance(report_t, (int, float)):
                if stage_t < report_t:
                    add_warning(
                        'confidence',
                        f'auto_stage_threshold ({stage_t}) < report_only_threshold ({report_t}). '
                        'This ordering may cause unexpected behavior.'
                    )

    # =========================================================================
    # [healers] section - OPTIONAL but validated if present
    # =========================================================================
    healers = config.get('healers', {})

    if healers and not isinstance(healers, dict):
        add_error('healers', f'Must be a section/dict, got {type(healers).__name__}',
                 'Use [healers.healer_name] in TOML')
    elif isinstance(healers, dict):
        for healer_name, healer_config in healers.items():
            prefix = f'healers.{healer_name}'

            # Type check healer config (Issue 3)
            if not isinstance(healer_config, dict):
                add_error(prefix, f'Must be a section/dict, got {type(healer_config).__name__}',
                         f'Use [{prefix}] section in TOML')
                continue

            # Validate 'enabled' field - handle string boolean issue (Issue 5 - TC-005, TC-009)
            if 'enabled' in healer_config:
                enabled_val = healer_config['enabled']
                if isinstance(enabled_val, str):
                    if enabled_val.lower() in ('false', 'no', '0'):
                        add_warning(f'{prefix}.enabled',
                                   f"String '{enabled_val}' is truthy in Python. Use boolean false (no quotes)")
                    elif enabled_val.lower() not in ('true', 'yes', '1'):
                        add_error(f'{prefix}.enabled', f"Invalid boolean string '{enabled_val}'",
                                 'Use true or false without quotes')

            # Validate regex patterns (Issue 7)
            # NOTE: backlink_format is a template string with {title} and {path}, NOT a regex
            for pattern_key in ['link_pattern', 'section_pattern']:
                if pattern_key in healer_config:
                    value = healer_config[pattern_key]
                    if isinstance(value, str):
                        try:
                            validate_regex_pattern(value, f'{prefix}.{pattern_key}')
                        except ConfigError as e:
                            add_error(f'{prefix}.{pattern_key}', str(e))

            # Validate pattern lists (Issue 4, 7)
            for pattern_list_key in ['timestamp_patterns', 'jargon_patterns']:
                if pattern_list_key in healer_config:
                    try:
                        patterns = ensure_list(healer_config[pattern_list_key], f'{prefix}.{pattern_list_key}')
                        if len(patterns) > MAX_PATTERNS:
                            add_error(f'{prefix}.{pattern_list_key}',
                                     f'Too many patterns ({len(patterns)}). Max is {MAX_PATTERNS}.',
                                     'Reduce pattern count or split configuration')
                        for i, pattern in enumerate(patterns):
                            try:
                                validate_regex_pattern(pattern, f'{prefix}.{pattern_list_key}[{i}]')
                            except ConfigError as e:
                                add_error(f'{prefix}.{pattern_list_key}[{i}]', str(e))
                    except ConfigError as e:
                        add_error(f'{prefix}.{pattern_list_key}', str(e))

            # Validate deprecated_patterns (list of dicts with pattern key)
            if 'deprecated_patterns' in healer_config:
                try:
                    dep_patterns = ensure_list(healer_config['deprecated_patterns'], f'{prefix}.deprecated_patterns')
                    if len(dep_patterns) > MAX_PATTERNS:
                        add_error(f'{prefix}.deprecated_patterns',
                                 f'Too many patterns ({len(dep_patterns)}). Max is {MAX_PATTERNS}.')
                    for i, item in enumerate(dep_patterns):
                        item_prefix = f'{prefix}.deprecated_patterns[{i}]'
                        if isinstance(item, dict):
                            if 'pattern' in item:
                                try:
                                    validate_regex_pattern(item['pattern'], f'{item_prefix}.pattern')
                                except ConfigError as e:
                                    add_error(f'{item_prefix}.pattern', str(e))
                            if 'confidence' in item:
                                try:
                                    validate_threshold(item['confidence'], f'{item_prefix}.confidence')
                                except ConfigError as e:
                                    add_error(f'{item_prefix}.confidence', str(e))
                        elif isinstance(item, str):
                            # Allow simple string patterns
                            try:
                                validate_regex_pattern(item, item_prefix)
                            except ConfigError as e:
                                add_error(item_prefix, str(e))
                        else:
                            add_error(item_prefix, f'Must be dict or string, got {type(item).__name__}')
                except ConfigError as e:
                    add_error(f'{prefix}.deprecated_patterns', str(e))

            # Validate numeric thresholds (Issue 2)
            threshold_configs = {
                'similarity_threshold': (0.0, 1.0),
                'fuzzy_threshold': (0.0, 1.0),
                'missing_keywords_threshold': (0.0, 1.0),
                'historical_success_rate': (0.0, 1.0),
            }
            for threshold_key, (min_val, max_val) in threshold_configs.items():
                if threshold_key in healer_config:
                    try:
                        validate_threshold(healer_config[threshold_key], f'{prefix}.{threshold_key}', min_val, max_val)
                    except ConfigError as e:
                        add_error(f'{prefix}.{threshold_key}', str(e))

            # Validate positive integer fields (Issue 2)
            int_fields = ['staleness_threshold_days', 'min_block_size', 'long_section_threshold']
            for int_key in int_fields:
                if int_key in healer_config:
                    value = healer_config[int_key]
                    try:
                        validate_positive_int(value, f'{prefix}.{int_key}')
                        # Warn about edge cases (Issue 2 - EV-018, EV-019, etc.)
                        if value == 0:
                            add_warning(f'{prefix}.{int_key}',
                                       f'Value is 0, which may cause all items to be flagged')
                    except ConfigError as e:
                        add_error(f'{prefix}.{int_key}', str(e))

            # Validate list fields (Issue 5)
            list_fields = ['exclude_dirs', 'file_extensions', 'hierarchy_rules', 'related_section_headers']
            for list_key in list_fields:
                if list_key in healer_config:
                    try:
                        items = ensure_list(healer_config[list_key], f'{prefix}.{list_key}')
                        if len(items) > MAX_ARRAY_SIZE:
                            add_error(f'{prefix}.{list_key}',
                                     f'Too many items ({len(items)}). Maximum is {MAX_ARRAY_SIZE}.',
                                     f'Reduce to fewer than {MAX_ARRAY_SIZE} items')
                    except ConfigError as e:
                        add_error(f'{prefix}.{list_key}', str(e))

            # Healer-specific validations
            if healer_name == 'sync_canonical':
                # source_file is required when enabled (Issue 6)
                enabled = healer_config.get('enabled', True)
                if enabled and 'source_file' not in healer_config:
                    add_error(f'{prefix}.source_file', 'Required when sync_canonical is enabled',
                             'Add source_file = "path/to/source.json"')
                elif 'source_file' in healer_config:
                    source_val = healer_config['source_file']
                    if not isinstance(source_val, str):
                        add_error(f'{prefix}.source_file', f'Must be string, got {type(source_val).__name__}')
                    # Only validate paths for ENABLED healers
                    elif enabled and check_paths and project.get('root'):
                        try:
                            source_path = Path(source_val)
                            root_path = Path(project['root'])
                            if str(project['root']).startswith('~'):
                                root_path = Path(os.path.expanduser(project['root']))
                            full_source = root_path / source_path if not source_path.is_absolute() else source_path
                            if not full_source.exists():
                                add_error(f'{prefix}.source_file',
                                         f'Source file does not exist: {full_source}',
                                         'Create the file or update the path')
                            # Path traversal check
                            validate_path_traversal(source_path, root_path, f'{prefix}.source_file')
                        except ConfigError as e:
                            add_error(f'{prefix}.source_file', str(e))

            if healer_name == 'enforce_disclosure':
                # layer_definitions validation
                if 'layer_definitions' in healer_config:
                    layers = healer_config['layer_definitions']
                    if not isinstance(layers, dict):
                        add_error(f'{prefix}.layer_definitions', f'Must be dict, got {type(layers).__name__}')
                    else:
                        for layer_name, layer_config in layers.items():
                            layer_prefix = f'{prefix}.layer_definitions.{layer_name}'
                            if not isinstance(layer_config, dict):
                                add_error(layer_prefix, f'Must be dict, got {type(layer_config).__name__}')
                                continue
                            # Validate layer-specific thresholds
                            if 'max_lines' in layer_config:
                                val = layer_config['max_lines']
                                try:
                                    validate_positive_int(val, f'{layer_prefix}.max_lines')
                                    if val == 0:
                                        add_warning(f'{layer_prefix}.max_lines',
                                                   'Value is 0, all sections will be flagged as oversized')
                                except ConfigError as e:
                                    add_error(f'{layer_prefix}.max_lines', str(e))
                            if 'allowed_depth' in layer_config:
                                val = layer_config['allowed_depth']
                                try:
                                    validate_positive_int(val, f'{layer_prefix}.allowed_depth')
                                    if val == 0:
                                        add_warning(f'{layer_prefix}.allowed_depth',
                                                   'Value is 0, all headers will be flagged as too deep')
                                except ConfigError as e:
                                    add_error(f'{layer_prefix}.allowed_depth', str(e))

            if healer_name == 'manage_collapsed':
                # hint_strategy validation
                # Valid values from manage_collapsed.py implementation
                if 'hint_strategy' in healer_config:
                    strategy = healer_config['hint_strategy']
                    valid_strategies = ['summary', 'first_sentence', 'keywords']
                    if strategy not in valid_strategies:
                        add_error(f'{prefix}.hint_strategy',
                                 f"Invalid value '{strategy}'",
                                 f'Use one of: {", ".join(valid_strategies)}')

    # =========================================================================
    # [git] section - OPTIONAL
    # =========================================================================
    git = config.get('git', {})

    if git and not isinstance(git, dict):
        add_error('git', f'Must be a section/dict, got {type(git).__name__}',
                 'Use [git] in TOML')
    elif isinstance(git, dict):
        if 'commit_prefix' in git:
            if not isinstance(git['commit_prefix'], str):
                add_error('git.commit_prefix', f"Must be string, got {type(git['commit_prefix']).__name__}",
                         'Use commit_prefix = "[docs]"')

        if 'auto_commit' in git:
            val = git['auto_commit']
            if isinstance(val, str) and val.lower() in ('false', 'no', '0'):
                add_warning('git.auto_commit', f"String '{val}' is truthy. Use boolean false")

        if 'install_hooks' in git:
            val = git['install_hooks']
            if isinstance(val, str) and val.lower() in ('false', 'no', '0'):
                add_warning('git.install_hooks', f"String '{val}' is truthy. Use boolean false")

    # =========================================================================
    # [reporting] section - OPTIONAL
    # =========================================================================
    reporting = config.get('reporting', {})

    if reporting and not isinstance(reporting, dict):
        add_error('reporting', f'Must be a section/dict, got {type(reporting).__name__}',
                 'Use [reporting] in TOML')
    elif isinstance(reporting, dict):
        if 'output_dir' in reporting:
            output_val = reporting['output_dir']
            if not isinstance(output_val, str):
                add_error('reporting.output_dir', f'Must be string, got {type(output_val).__name__}')
            elif project.get('root'):
                try:
                    output_dir = Path(output_val)
                    root_path = Path(project['root'])
                    if str(project['root']).startswith('~'):
                        root_path = Path(os.path.expanduser(project['root']))
                    # Path traversal check (warning, not error - output dir can be created)
                    if '..' in output_val:
                        add_warning('reporting.output_dir',
                                   f"Path contains '..', may escape project root")
                except Exception as e:
                    add_warning('reporting.output_dir', str(e))

        if 'format' in reporting:
            fmt = reporting['format']
            # Valid values from reporting.py implementation (supports 'both' for markdown+json)
            valid_formats = ['markdown', 'json', 'html', 'both']
            if fmt not in valid_formats:
                add_error('reporting.format', f"Invalid format '{fmt}'",
                         f'Use one of: {", ".join(valid_formats)}')

    # =========================================================================
    # [advanced] section - Check for unimplemented features
    # =========================================================================
    advanced = config.get('advanced', {})
    if advanced and isinstance(advanced, dict):
        unimplemented = ['max_workers', 'cache_dir', 'enable_cache', 'cache_ttl']
        for key in unimplemented:
            if key in advanced:
                add_warning(f'advanced.{key}', 'This feature is documented but not yet implemented')

    # =========================================================================
    # Final result
    # =========================================================================
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        validated_config=config if len(errors) == 0 else {}
    )


def safe_read_file(path: Path, max_size: int = MAX_FILE_SIZE) -> str:
    """
    Safely read a file with size limits.

    Args:
        path: Path to file
        max_size: Maximum file size in bytes

    Returns:
        File contents

    Raises:
        ValueError: If file exceeds size limit
        FileNotFoundError: If file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    size = path.stat().st_size
    if size > max_size:
        raise ValueError(
            f"File too large: {path} ({size:,} bytes). "
            f"Maximum allowed: {max_size:,} bytes"
        )

    return path.read_text()


def validate_and_load_config(
    config_path: Path,
    check_paths: bool = True
) -> Tuple[Dict[str, Any], ValidationResult]:
    """
    Load and validate a configuration file.

    This is the main entry point for config validation. It:
    1. Checks file exists and is valid size
    2. Parses YAML/TOML with proper error handling
    3. Runs comprehensive validation
    4. Returns both config and validation result

    Args:
        config_path: Path to config file (YAML, TOML, or JSON)
        check_paths: If True, verify paths exist on disk

    Returns:
        (config_dict, validation_result)

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config format is unsupported
        ConfigValidationError: If config is invalid (when using raise_if_invalid)
    """
    # Check file exists
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Check file size (Issue 4 - Resource limits)
    file_size = config_path.stat().st_size
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise ValueError(
            f"Config file too large: {config_path} ({file_size:,} bytes). "
            f"Maximum is 10MB."
        )

    if file_size == 0:
        raise ValueError(f"Config file is empty: {config_path}")

    # Load based on extension
    suffix = config_path.suffix.lower()
    config = None
    parse_error = None

    if suffix in ['.yaml', '.yml']:
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except ImportError:
            raise ValueError(
                "YAML support requires PyYAML. Install with: pip install pyyaml"
            )
        except yaml.YAMLError as e:
            parse_error = f"YAML parse error: {e}"

    elif suffix == '.toml':
        try:
            try:
                import tomllib
            except ImportError:
                import toml as tomllib
            with open(config_path, 'rb') as f:
                config = tomllib.load(f)
        except ImportError:
            raise ValueError(
                "TOML support requires toml. Install with: pip install toml"
            )
        except Exception as e:
            parse_error = f"TOML parse error: {e}"

    elif suffix == '.json':
        import json
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            parse_error = f"JSON parse error at line {e.lineno}: {e.msg}"

    else:
        raise ValueError(
            f"Unsupported config format: {suffix}. "
            f"Use .yaml, .yml, .toml, or .json"
        )

    # Handle parse errors
    if parse_error:
        return {}, ValidationResult(
            is_valid=False,
            errors=[f"[config_file] {parse_error}"],
            warnings=[],
            validated_config={}
        )

    if not isinstance(config, dict):
        return {}, ValidationResult(
            is_valid=False,
            errors=["[config] Config must be a dictionary/mapping, got " + type(config).__name__],
            warnings=[],
            validated_config={}
        )

    # Validate using the config file's parent as project root for relative paths
    project_root = config_path.parent
    result = validate_config_schema(config, project_root=project_root, check_paths=check_paths)

    return config, result


def load_config_strict(config_path: Path) -> Dict[str, Any]:
    """
    Load config and raise immediately if validation fails.

    Convenience function for use in CLI tools where you want to fail fast.

    Args:
        config_path: Path to config file

    Returns:
        Validated configuration dictionary

    Raises:
        ConfigValidationError: If any validation errors occur
        FileNotFoundError: If config file doesn't exist
        ValueError: If config format is unsupported
    """
    config, result = validate_and_load_config(config_path)

    if not result.is_valid:
        raise ConfigValidationError(result.errors, result.warnings)

    # Log warnings
    for warning in result.warnings:
        logger.warning(f"Config warning: {warning}")

    return config
