"""
Regex validator with ReDoS (Regular Expression Denial of Service) protection.

Validates regex patterns for potential exponential backtracking that could
cause performance issues or denial of service attacks.
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


class RegexSecurityError(Exception):
    """Raised when a regex pattern has security concerns (ReDoS)."""
    pass


class RegexConfigError(Exception):
    """Raised when a regex pattern is invalid."""
    pass


@dataclass
class RegexIssue:
    """Issue found in regex pattern."""
    pattern: str
    severity: str  # 'high', 'medium', 'low'
    issue_type: str
    description: str
    line_number: Optional[int] = None


class RegexValidator:
    """Validates regex patterns for ReDoS vulnerabilities."""

    # Patterns that indicate potential ReDoS
    REDOS_PATTERNS = [
        # Nested quantifiers: (a+)+, (a*)*
        (r'\([^)]*[+*]\)[+*]', 'high', 'nested_quantifiers',
         'Nested quantifiers can cause exponential backtracking'),

        # Overlapping alternations: (a|a)+, (ab|a)+
        (r'\([^)]*\|[^)]*\)[+*]', 'medium', 'alternation_quantifier',
         'Alternation with quantifier may cause backtracking'),

        # Repeated capturing groups: (.*)+
        (r'\([^)]*\.\*[^)]*\)[+*]', 'high', 'repeated_wildcards',
         'Repeated wildcard capturing groups are dangerous'),

        # Unanchored patterns with wildcards
        (r'^[^$]*\.\*[^$]*$', 'low', 'unanchored_wildcard',
         'Unanchored wildcard may be inefficient'),
    ]

    def __init__(self, max_pattern_length: int = 500):
        """
        Initialize validator.

        Args:
            max_pattern_length: Maximum allowed pattern length
        """
        self.max_pattern_length = max_pattern_length

    def validate_pattern(self, pattern: str, context: str = "") -> List[RegexIssue]:
        """
        Validate a single regex pattern.

        Args:
            pattern: The regex pattern to validate
            context: Optional context (e.g., healer name, line number)

        Returns:
            List of issues found
        """
        issues = []

        # Check pattern length
        if len(pattern) > self.max_pattern_length:
            issues.append(RegexIssue(
                pattern=pattern,
                severity='medium',
                issue_type='excessive_length',
                description=f'Pattern exceeds {self.max_pattern_length} characters'
            ))

        # Check for ReDoS patterns
        for redos_pattern, severity, issue_type, description in self.REDOS_PATTERNS:
            if re.search(redos_pattern, pattern):
                issues.append(RegexIssue(
                    pattern=pattern,
                    severity=severity,
                    issue_type=issue_type,
                    description=description
                ))

        # Try to compile the pattern
        try:
            re.compile(pattern)
        except re.error as e:
            issues.append(RegexIssue(
                pattern=pattern,
                severity='high',
                issue_type='invalid_syntax',
                description=f'Pattern is invalid: {str(e)}'
            ))

        return issues

    def validate_config_patterns(self, config: dict) -> List[RegexIssue]:
        """
        Validate all regex patterns in a configuration.

        Args:
            config: Configuration dictionary

        Returns:
            List of all issues found
        """
        all_issues = []

        # Check deprecated_commands in detect_staleness config
        staleness_config = config.get('healers', {}).get('detect_staleness', {})
        if 'deprecated_commands' in staleness_config:
            for pattern_config in staleness_config['deprecated_commands']:
                pattern = pattern_config.get('pattern', '')
                context = f"detect_staleness.deprecated_commands.{pattern_config.get('name', 'unknown')}"
                issues = self.validate_pattern(pattern, context)
                all_issues.extend(issues)

        # Check custom_patterns in any healer
        for healer_name, healer_config in config.get('healers', {}).items():
            if 'custom_patterns' in healer_config:
                for pattern in healer_config['custom_patterns']:
                    context = f"{healer_name}.custom_patterns"
                    issues = self.validate_pattern(pattern, context)
                    all_issues.extend(issues)

        return all_issues

    def sanitize_pattern(self, pattern: str) -> str:
        """
        Attempt to sanitize a potentially dangerous pattern.

        Args:
            pattern: Original pattern

        Returns:
            Sanitized pattern (may be the same if no issues found)
        """
        # Remove nested quantifiers by simplifying to single quantifier
        sanitized = re.sub(r'\(([^)]+)[+*]\)[+*]', r'(\1)+', pattern)

        # Anchor wildcard patterns
        if '.*' in sanitized and not (sanitized.startswith('^') or sanitized.endswith('$')):
            sanitized = f'^{sanitized}$'

        return sanitized


def validate_regex_safety(pattern: str, max_length: int = 500) -> Tuple[bool, List[str]]:
    """
    Quick validation function for regex safety.

    Args:
        pattern: Regex pattern to validate
        max_length: Maximum allowed pattern length

    Returns:
        Tuple of (is_safe, list_of_warnings)
    """
    validator = RegexValidator(max_pattern_length=max_length)
    issues = validator.validate_pattern(pattern)

    is_safe = not any(issue.severity == 'high' for issue in issues)
    warnings = [f"[{issue.severity}] {issue.description}" for issue in issues]

    return is_safe, warnings
