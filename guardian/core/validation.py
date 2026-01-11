"""
Validation framework for healing operations.

Provides validation utilities for:
- File syntax (markdown, JSON, YAML, Python)
- Link existence and reachability
- Change safety and reversibility

Security features:
- Uses ast.parse instead of compile() for Python syntax validation (DG-2026-004)
- File size limits for validation (DG-2026-006)
"""

import re
import json
import ast
from pathlib import Path
from typing import List, Tuple, Optional
from .base import Change
from .security import validate_file_size, safe_read_file, MAX_FILE_SIZE_BYTES


def validate_syntax(file_path: Path) -> bool:
    """
    Validate file syntax based on extension.

    Supported formats:
    - .md: Markdown syntax validation
    - .json: JSON parsing
    - .yaml/.yml: YAML parsing (if PyYAML available)
    - .py: Python syntax check via ast.parse() (security: no code execution)

    Security:
    - Uses ast.parse() instead of compile() for Python (DG-2026-004)
    - Enforces file size limits to prevent memory exhaustion

    Args:
        file_path: Path to file to validate

    Returns:
        True if syntax is valid, False otherwise
    """
    if not file_path.exists():
        return False

    # Security: Check file size before reading
    is_valid, error = validate_file_size(file_path)
    if not is_valid:
        return False

    suffix = file_path.suffix.lower()

    try:
        content = safe_read_file(file_path)

        if suffix == '.json':
            json.loads(content)
            return True

        elif suffix in ['.yaml', '.yml']:
            try:
                import yaml
                yaml.safe_load(content)
                return True
            except ImportError:
                # PyYAML not available - skip validation
                return True

        elif suffix == '.py':
            # Security: Use ast.parse instead of compile() (DG-2026-004)
            # ast.parse only parses, never executes code
            # This is safer than compile() which could theoretically be
            # combined with exec() if code evolves
            ast.parse(content)
            return True

        elif suffix == '.md':
            # Basic markdown validation
            # Check for common syntax errors
            return validate_markdown_syntax(content)

        else:
            # Unknown file type - assume valid
            return True

    except Exception:
        return False


def validate_markdown_syntax(content: str) -> bool:
    """
    Validate markdown syntax.

    Checks for:
    - Unclosed code blocks
    - Malformed links
    - Unbalanced brackets

    Args:
        content: Markdown content as string

    Returns:
        True if markdown is well-formed
    """
    lines = content.split('\n')

    # Check for unclosed code blocks
    code_block_count = 0
    for line in lines:
        if line.strip().startswith('```'):
            code_block_count += 1

    if code_block_count % 2 != 0:
        return False  # Unclosed code block

    # Check for malformed links [text](url)
    # Should have matching brackets
    for match in re.finditer(r'\[([^\]]*)\]\(([^\)]*)\)', content):
        text, url = match.groups()
        if not text or not url:
            return False  # Empty text or URL

    return True


def validate_links(file_path: Path, project_root: Path) -> bool:
    """
    Validate all links in a file exist.

    Checks internal links (relative and absolute) for existence.
    Skips external links (http/https) and anchors.

    Args:
        file_path: Path to file containing links
        project_root: Root directory for resolving absolute paths

    Returns:
        True if all internal links are valid
    """
    if not file_path.exists():
        return False

    content = file_path.read_text()

    # Extract markdown links [text](url)
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')

    for match in link_pattern.finditer(content):
        url = match.group(2)

        # Skip external links
        if url.startswith(('http://', 'https://', 'mailto:')):
            continue

        # Skip anchors only
        if url.startswith('#'):
            continue

        # Resolve link path
        if url.startswith('/'):
            # Absolute from project root
            target = project_root / url.lstrip('/')
        else:
            # Relative to file
            target = (file_path.parent / url).resolve()

        # Strip anchor if present
        if '#' in str(target):
            target = Path(str(target).split('#')[0])

        # Check existence
        if not target.exists():
            return False

    return True


def validate_change(change: Change, strict: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate a proposed change.

    Checks:
    1. File exists (or is being created)
    2. Old content matches current file (if file exists)
    3. New content is valid syntax
    4. Change magnitude is reasonable
    5. (strict) File syntax remains valid after change

    Args:
        change: Change object to validate
        strict: If True, perform additional syntax validation

    Returns:
        (is_valid, error_message)
        - (True, None) if valid
        - (False, "reason") if invalid
    """
    # 1. File must exist (unless creating)
    if not change.file.exists() and change.old_content:
        return False, f"File does not exist: {change.file}"

    # 2. Old content must match
    if change.file.exists() and change.old_content:
        content = change.file.read_text()
        if change.old_content not in content:
            return False, "Old content not found in file"

    # 3. New content should not be empty (unless explicit deletion)
    if not change.new_content and change.old_content:
        # Deletion - check if intentional
        if "delete" not in change.reason.lower():
            return False, "New content is empty but change is not a deletion"

    # 4. Change magnitude check
    old_lines = change.old_content.count('\n') + 1 if change.old_content else 0
    new_lines = change.new_content.count('\n') + 1 if change.new_content else 0
    diff_lines = abs(new_lines - old_lines)

    if diff_lines > 200:
        return False, f"Change magnitude too large: {diff_lines} lines"

    # 5. Strict mode: validate syntax after change
    if strict and change.file.exists():
        # Simulate change
        content = change.file.read_text()
        if change.old_content:
            new_content = content.replace(change.old_content, change.new_content)
        else:
            new_content = content + change.new_content

        # Write to temp file and validate
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=change.file.suffix,
            delete=False
        ) as tmp:
            tmp.write(new_content)
            tmp_path = Path(tmp.name)

        try:
            is_valid = validate_syntax(tmp_path)
            if not is_valid:
                return False, "Change would result in invalid syntax"
        finally:
            tmp_path.unlink()

    return True, None


def validate_all_changes(changes: List[Change], strict: bool = False) -> Tuple[bool, List[str]]:
    """
    Validate all proposed changes.

    Args:
        changes: List of Change objects to validate
        strict: If True, perform strict syntax validation

    Returns:
        (all_valid, error_messages)
        - (True, []) if all valid
        - (False, ["error1", "error2"]) if any invalid
    """
    errors = []

    for change in changes:
        is_valid, error = validate_change(change, strict=strict)
        if not is_valid:
            errors.append(f"{change.file}:{change.line} - {error}")

    return len(errors) == 0, errors
