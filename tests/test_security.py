"""
Security tests for Doc Guardian.

Tests path traversal prevention, ReDoS protection, and other security features.
"""

import pytest
from pathlib import Path
import tempfile
import os

from doc_guardian.core.path_validator import PathValidator, PathTraversalError, validate_file_path
from doc_guardian.core.regex_validator import RegexValidator, validate_regex_safety


class TestPathValidator:
    """Test path validation and traversal prevention."""

    def test_basic_validation(self):
        """Test basic path validation within allowed root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validator = PathValidator(allowed_roots=[root])

            # Valid path within root
            valid_path = root / "docs" / "file.md"
            result = validator.validate_path(valid_path)
            assert result.is_absolute()

    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validator = PathValidator(allowed_roots=[root])

            # Attempt to escape using ../
            evil_path = root / ".." / ".." / "etc" / "passwd"
            with pytest.raises(PathTraversalError):
                validator.validate_path(evil_path)

    def test_absolute_path_outside_root(self):
        """Test that absolute paths outside root are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validator = PathValidator(allowed_roots=[root])

            # Absolute path outside allowed root
            evil_path = Path("/etc/passwd")
            with pytest.raises(PathTraversalError):
                validator.validate_path(evil_path)

    def test_symlink_rejection(self):
        """Test that symlinks are rejected by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validator = PathValidator(allowed_roots=[root], follow_symlinks=False)

            # Create a symlink
            real_file = root / "real.txt"
            real_file.write_text("content")
            symlink = root / "link.txt"
            os.symlink(real_file, symlink)

            with pytest.raises(PathTraversalError):
                validator.validate_path(symlink)

    def test_symlink_allowed(self):
        """Test that symlinks can be allowed if configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validator = PathValidator(allowed_roots=[root], follow_symlinks=True)

            # Create a symlink
            real_file = root / "real.txt"
            real_file.write_text("content")
            symlink = root / "link.txt"
            os.symlink(real_file, symlink)

            # Should work when follow_symlinks=True
            result = validator.validate_path(symlink)
            assert result.is_absolute()

    def test_null_byte_injection(self):
        """Test that null byte injection is blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validator = PathValidator(allowed_roots=[root])

            # Path with null byte
            evil_path = f"{root}/file.txt\x00.md"
            with pytest.raises(PathTraversalError):
                validator.validate_path(Path(evil_path))

    def test_safe_filename(self):
        """Test filename safety checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validator = PathValidator(allowed_roots=[root])

            # Safe filenames
            assert validator.is_safe_filename("file.md")
            assert validator.is_safe_filename("my-doc.txt")

            # Unsafe filenames
            assert not validator.is_safe_filename("../etc/passwd")
            assert not validator.is_safe_filename(".")
            assert not validator.is_safe_filename("..")
            assert not validator.is_safe_filename("file\x00.md")

    def test_multiple_roots(self):
        """Test validation with multiple allowed roots."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                root1 = Path(tmpdir1)
                root2 = Path(tmpdir2)
                validator = PathValidator(allowed_roots=[root1, root2])

                # Valid in first root
                path1 = root1 / "file.md"
                result1 = validator.validate_path(path1)
                assert result1.is_absolute()

                # Valid in second root
                path2 = root2 / "file.md"
                result2 = validator.validate_path(path2)
                assert result2.is_absolute()

    def test_quick_validation_function(self):
        """Test the quick validation helper function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Valid path
            valid_path = root / "file.md"
            assert validate_file_path(valid_path, [root])

            # Invalid path
            invalid_path = Path("/etc/passwd")
            assert not validate_file_path(invalid_path, [root])


class TestRegexValidator:
    """Test regex validation and ReDoS prevention."""

    def test_basic_validation(self):
        """Test basic regex validation."""
        validator = RegexValidator()

        # Valid, safe pattern
        issues = validator.validate_pattern(r'^\d{3}-\d{4}$')
        assert len(issues) == 0

    def test_nested_quantifiers(self):
        """Test detection of nested quantifiers (ReDoS vulnerability)."""
        validator = RegexValidator()

        # Dangerous nested quantifiers
        issues = validator.validate_pattern(r'(a+)+')
        assert len(issues) > 0
        assert any(issue.severity == 'high' for issue in issues)
        assert any('nested' in issue.issue_type for issue in issues)

    def test_repeated_wildcards(self):
        """Test detection of repeated wildcard groups."""
        validator = RegexValidator()

        # Dangerous repeated wildcards
        issues = validator.validate_pattern(r'(.*)+')
        assert len(issues) > 0
        assert any(issue.severity == 'high' for issue in issues)

    def test_alternation_quantifier(self):
        """Test detection of alternation with quantifiers."""
        validator = RegexValidator()

        # Potentially dangerous alternation
        issues = validator.validate_pattern(r'(a|ab)+')
        assert len(issues) > 0

    def test_invalid_syntax(self):
        """Test detection of invalid regex syntax."""
        validator = RegexValidator()

        # Invalid pattern
        issues = validator.validate_pattern(r'[a-z')
        assert len(issues) > 0
        assert any(issue.severity == 'high' for issue in issues)
        assert any('invalid_syntax' in issue.issue_type for issue in issues)

    def test_excessive_length(self):
        """Test detection of excessively long patterns."""
        validator = RegexValidator(max_pattern_length=50)

        # Pattern exceeding limit
        long_pattern = 'a' * 100
        issues = validator.validate_pattern(long_pattern)
        assert len(issues) > 0
        assert any('excessive_length' in issue.issue_type for issue in issues)

    def test_config_validation(self):
        """Test validation of patterns in config."""
        validator = RegexValidator()

        config = {
            'healers': {
                'detect_staleness': {
                    'deprecated_commands': [
                        {
                            'name': 'docker-compose',
                            'pattern': r'docker-compose\s+',  # Safe
                        },
                        {
                            'name': 'dangerous',
                            'pattern': r'(a+)+',  # Dangerous
                        }
                    ]
                }
            }
        }

        issues = validator.validate_config_patterns(config)
        assert len(issues) > 0
        assert any(issue.severity == 'high' for issue in issues)

    def test_pattern_sanitization(self):
        """Test regex pattern sanitization."""
        validator = RegexValidator()

        # Sanitize nested quantifiers
        dangerous = r'(a+)+'
        sanitized = validator.sanitize_pattern(dangerous)
        assert sanitized != dangerous

        # Anchor unanchored wildcards
        unanchored = r'.*test.*'
        sanitized = validator.sanitize_pattern(unanchored)
        assert sanitized.startswith('^') or sanitized.endswith('$')

    def test_quick_validation_function(self):
        """Test the quick validation helper function."""
        # Safe pattern
        is_safe, warnings = validate_regex_safety(r'^\d{3}$')
        assert is_safe
        assert len(warnings) == 0

        # Dangerous pattern
        is_safe, warnings = validate_regex_safety(r'(a+)+')
        assert not is_safe
        assert len(warnings) > 0


class TestIntegration:
    """Integration tests for security features."""

    def test_healer_uses_path_validation(self):
        """Test that healers use path validation in practice."""
        # This would test actual healer integration
        # For now, just verify the validators can be imported and used
        from doc_guardian.core.path_validator import create_doc_path_validator

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            doc_root = root / "docs"
            doc_root.mkdir()

            validator = create_doc_path_validator(root, doc_root)
            assert validator is not None

    def test_config_loader_validates_patterns(self):
        """Test that config loading validates regex patterns."""
        # This would test the config loader integration
        # Placeholder for actual integration test
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
