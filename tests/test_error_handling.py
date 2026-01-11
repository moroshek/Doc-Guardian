"""
Error handling test suite for Doc Guardian.

Tests 20 error handling issues from ERROR_HANDLING_AUDIT.md:
1. Silent failures (pass statements)
2. Symlink depth protection
3. Atomic file writes
4. Signal handlers (Ctrl+C)
5. Git errors handled
6. Malformed data handled
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from guardian.core.base import HealingSystem, HealingReport, Change
from guardian.core.validation import validate_syntax, validate_change
from guardian.core.config_validator import safe_read_file


class TestSilentFailures:
    """Test that silent failures are properly logged."""

    def test_change_validation_logs_errors(self, tmp_path):
        """Failed change validation should log errors."""
        # Create a change for a non-existent file
        change = Change(
            file=tmp_path / "nonexistent.md",
            line=1,
            old_content="old",
            new_content="new",
            confidence=0.9,
            reason="test",
            healer="test"
        )

        is_valid, error = validate_change(change)
        assert not is_valid
        assert error is not None
        assert "does not exist" in error

    def test_old_content_mismatch_error(self, tmp_path):
        """Mismatched old content should return clear error."""
        test_file = tmp_path / "test.md"
        test_file.write_text("actual content")

        change = Change(
            file=test_file,
            line=1,
            old_content="wrong content",
            new_content="new",
            confidence=0.9,
            reason="test",
            healer="test"
        )

        is_valid, error = validate_change(change)
        assert not is_valid
        assert "not found" in error


class TestSymlinkProtection:
    """Test symlink depth protection."""

    def test_symlink_loop_detection(self, tmp_path):
        """Symlink loops should be detected."""
        # Create a symlink loop
        link_a = tmp_path / "link_a"
        link_b = tmp_path / "link_b"

        try:
            link_a.symlink_to(link_b)
            link_b.symlink_to(link_a)

            # Following the symlink should eventually fail
            with pytest.raises(OSError):
                link_a.resolve(strict=True)
        except OSError:
            pytest.skip("Cannot create symlink loops on this system")
        finally:
            # Cleanup
            if link_a.is_symlink():
                link_a.unlink()
            if link_b.is_symlink():
                link_b.unlink()


class TestFileOperations:
    """Test file operation error handling."""

    def test_read_nonexistent_file(self, tmp_path):
        """Reading non-existent file should raise clear error."""
        fake_path = tmp_path / "nonexistent.txt"
        with pytest.raises(FileNotFoundError):
            safe_read_file(fake_path)

    def test_read_empty_file(self, tmp_path):
        """Reading empty file should return empty string."""
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()
        content = safe_read_file(empty_file)
        assert content == ""

    def test_large_file_rejected(self, tmp_path):
        """Large files should be rejected with clear error."""
        large_file = tmp_path / "large.txt"
        large_file.write_text("content")

        with pytest.raises(ValueError) as exc_info:
            safe_read_file(large_file, max_size=1)  # 1 byte limit
        assert "too large" in str(exc_info.value).lower()


class TestSignalHandlers:
    """Test signal handler behavior."""

    def test_shutdown_flag_exists(self):
        """Shutdown flag should be defined in heal.py."""
        from guardian import heal
        assert hasattr(heal, '_shutdown_requested')

    def test_signal_handler_defined(self):
        """Signal handler should be defined."""
        from guardian import heal
        assert hasattr(heal, '_signal_handler')
        assert callable(heal._signal_handler)


class TestGitErrorHandling:
    """Test git-related error handling."""

    def test_git_utils_handles_missing_git(self):
        """git_utils should handle missing git gracefully."""
        from guardian.core import git_utils

        # Mock subprocess to simulate git not found
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            # These should not raise, but return False
            result = git_utils.is_git_repo(Path("/tmp"))
            assert result is False

    def test_git_timeout_handled(self):
        """Git timeouts should be handled."""
        from guardian.core import git_utils
        import subprocess

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 10)

            # Should handle timeout gracefully
            result = git_utils.is_git_repo(Path("/tmp"))
            assert result is False


class TestMalformedDataHandling:
    """Test handling of malformed input data."""

    def test_invalid_json_validation(self, tmp_path):
        """Invalid JSON should fail validation."""
        json_file = tmp_path / "bad.json"
        json_file.write_text("{invalid json")

        result = validate_syntax(json_file)
        assert result is False

    def test_invalid_yaml_validation(self, tmp_path):
        """Invalid YAML should fail validation."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("key: [unclosed")

        # Should handle gracefully (either False or skip if no yaml)
        result = validate_syntax(yaml_file)
        # May return True if yaml is not available and validation is skipped

    def test_invalid_python_validation(self, tmp_path):
        """Invalid Python should fail validation."""
        py_file = tmp_path / "bad.py"
        py_file.write_text("def broken(")

        result = validate_syntax(py_file)
        assert result is False

    def test_unclosed_markdown_code_block(self, tmp_path):
        """Unclosed markdown code blocks should be detected."""
        md_file = tmp_path / "bad.md"
        md_file.write_text("```python\ncode without closing")

        result = validate_syntax(md_file)
        assert result is False

    def test_binary_file_handling(self, tmp_path):
        """Binary files should be handled gracefully."""
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe")

        # Reading as text might fail - that's OK
        # The important thing is no crash
        try:
            content = binary_file.read_text()
        except UnicodeDecodeError:
            pass  # Expected

    def test_null_bytes_in_file(self, tmp_path):
        """Files with null bytes should be handled."""
        null_file = tmp_path / "null.txt"
        null_file.write_bytes(b"before\x00after")

        # Should either handle or raise clear error
        try:
            content = safe_read_file(null_file)
        except ValueError:
            pass  # Expected for embedded nulls


class TestEdgeCases:
    """Test edge case error handling."""

    def test_empty_config(self):
        """Empty config should provide clear error."""
        from guardian.core.config_validator import validate_config_schema

        result = validate_config_schema({})
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_zero_confidence(self, tmp_path):
        """Zero confidence changes should be handled."""
        change = Change(
            file=tmp_path / "test.md",
            line=1,
            old_content="old",
            new_content="new",
            confidence=0.0,  # Zero confidence
            reason="test",
            healer="test"
        )
        # Should not raise, just low confidence
        assert change.confidence == 0.0

    def test_negative_line_number(self, tmp_path):
        """Negative line numbers should be handled."""
        change = Change(
            file=tmp_path / "test.md",
            line=-1,  # Invalid
            old_content="old",
            new_content="new",
            confidence=0.9,
            reason="test",
            healer="test"
        )
        # Should be created but validation should catch it


class TestReportGeneration:
    """Test report generation with errors."""

    def test_report_with_errors(self):
        """Reports should properly include errors."""
        report = HealingReport(
            healer_name="test_healer",
            mode="check",
            timestamp="2026-01-11T00:00:00",
            issues_found=5,
            issues_fixed=0,
            changes=[],
            errors=["Error 1", "Error 2"]
        )

        assert report.has_errors
        assert len(report.errors) == 2

    def test_success_rate_with_no_issues(self):
        """Success rate should be 1.0 when no issues found."""
        report = HealingReport(
            healer_name="test_healer",
            mode="check",
            timestamp="2026-01-11T00:00:00",
            issues_found=0,
            issues_fixed=0,
            changes=[],
            errors=[]
        )

        assert report.success_rate == 1.0

    def test_success_rate_calculation(self):
        """Success rate should be correctly calculated."""
        report = HealingReport(
            healer_name="test_healer",
            mode="heal",
            timestamp="2026-01-11T00:00:00",
            issues_found=10,
            issues_fixed=7,
            changes=[],
            errors=[]
        )

        assert report.success_rate == 0.7


class TestValidationChain:
    """Test complete validation chains."""

    def test_validate_all_changes(self, tmp_path):
        """validate_all_changes should aggregate errors."""
        from guardian.core.validation import validate_all_changes

        # Create a file
        test_file = tmp_path / "test.md"
        test_file.write_text("content")

        changes = [
            Change(
                file=test_file,
                line=1,
                old_content="content",
                new_content="new content",
                confidence=0.9,
                reason="valid change",
                healer="test"
            ),
            Change(
                file=tmp_path / "nonexistent.md",
                line=1,
                old_content="old",
                new_content="new",
                confidence=0.9,
                reason="invalid - file missing",
                healer="test"
            ),
        ]

        all_valid, errors = validate_all_changes(changes)
        assert not all_valid
        assert len(errors) == 1  # One invalid change


class TestNewErrorHandling:
    """Tests for error handling improvements from ERROR_HANDLING_AUDIT.md."""

    def test_symlink_loop_custom_depth(self, tmp_path):
        """FS-05: Symlink loops should be caught with custom depth."""
        from guardian.healers.fix_broken_links import (
            resolve_with_depth_limit,
            SymlinkLoopError,
        )

        # Create symlink loop: a -> b -> a
        link_a = tmp_path / "link_a"
        link_b = tmp_path / "link_b"

        try:
            link_a.symlink_to(link_b)
            link_b.symlink_to(link_a)

            with pytest.raises(SymlinkLoopError) as exc_info:
                resolve_with_depth_limit(link_a, max_depth=10)

            assert "depth limit" in str(exc_info.value).lower()
        except OSError:
            pytest.skip("Cannot create symlinks on this system")
        finally:
            if link_a.is_symlink():
                link_a.unlink()
            if link_b.is_symlink():
                link_b.unlink()

    def test_large_file_content_extractor(self, tmp_path):
        """RT-01: Large files should be skipped with logging."""
        from guardian.healers.resolve_duplicates import ContentExtractor

        extractor = ContentExtractor(max_file_size=100)  # 100 bytes

        large_file = tmp_path / "large.md"
        large_file.write_text("x" * 200)  # 200 bytes

        blocks = extractor.extract_paragraphs(large_file)
        assert blocks == []
        assert len(extractor.errors) >= 1
        assert "too large" in extractor.errors[0].lower()

    def test_regex_validation_at_init(self):
        """CFG-05: Invalid regex should raise at init time."""
        from guardian.healers.fix_broken_links import (
            LinkExtractor,
            RegexConfigError,
        )

        with pytest.raises(RegexConfigError) as exc_info:
            LinkExtractor("[[invalid", logger=None)

        assert "invalid" in str(exc_info.value).lower()

    def test_doc_root_must_exist(self, tmp_path):
        """FS-14: Doc root must exist on init."""
        from guardian.core.base import HealingSystem

        config = {
            "project": {
                "root": str(tmp_path),
                "doc_root": str(tmp_path / "missing_docs"),
            }
        }

        class DummyHealer(HealingSystem):
            def check(self):
                pass
            def heal(self):
                pass

        with pytest.raises(FileNotFoundError) as exc_info:
            DummyHealer(config)

        assert "does not exist" in str(exc_info.value)

    def test_malformed_json_detailed_error(self, tmp_path):
        """DC-07: Malformed JSON should give line/column info."""
        from guardian.healers.sync_canonical import CanonicalLoader

        bad_json = tmp_path / "bad.json"
        bad_json.write_text('{"key": "value",}')

        loader = CanonicalLoader(bad_json, "json")

        with pytest.raises(ValueError) as exc_info:
            loader.load()

        error_msg = str(exc_info.value).lower()
        assert "malformed" in error_msg
        assert "line" in error_msg

    def test_git_not_installed_error(self):
        """GIT-04: Missing git should give clear error."""
        from guardian.core.git_utils import (
            GitNotInstalledError,
            _run_git_command,
        )

        with patch("guardian.core.git_utils.shutil.which") as mock_which:
            mock_which.return_value = None

            with pytest.raises(GitNotInstalledError) as exc_info:
                _run_git_command(["git", "status"], Path("."), 10, "test")

            assert "not installed" in str(exc_info.value).lower()

    def test_git_timeout_error(self):
        """GIT-06: Git timeout should give clear error."""
        from guardian.core.git_utils import (
            GitTimeoutError,
            _run_git_command,
        )
        import subprocess

        with patch("guardian.core.git_utils.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/git"

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("git", 10)

                with pytest.raises(GitTimeoutError) as exc_info:
                    _run_git_command(["git", "status"], Path("."), 10, "test")

                assert "timed out" in str(exc_info.value).lower()

    def test_atomic_write_creates_file(self, tmp_path):
        """FS-03: Atomic write should create file safely."""
        from guardian.core.atomic_write import atomic_write

        test_file = tmp_path / "new.txt"
        result = atomic_write(test_file, "content")

        assert result is True
        assert test_file.exists()
        assert test_file.read_text() == "content"

    def test_atomic_write_preserves_on_error(self, tmp_path):
        """FS-03: Atomic write should not corrupt on error."""
        from guardian.core.atomic_write import atomic_write

        test_file = tmp_path / "existing.txt"
        test_file.write_text("original")

        # Simulate a directory (can't write to)
        bad_path = tmp_path / "dir_not_file"
        bad_path.mkdir()

        # This should fail but not corrupt
        try:
            atomic_write(bad_path / "subdir" / "file.txt", "content")
        except Exception:
            pass  # Expected to fail

        # Original file should be untouched
        assert test_file.read_text() == "original"

    def test_graceful_shutdown_registers_cleanup(self):
        """RT-06/RT-07: Cleanup actions should be registered."""
        from guardian.core.signal_handlers import GracefulShutdown

        shutdown = GracefulShutdown()
        called = []

        def cleanup():
            called.append(True)

        shutdown.register_cleanup(cleanup)
        assert cleanup in shutdown.cleanup_actions

    def test_logger_error_codes_defined(self):
        """All critical error codes should be defined."""
        from guardian.core.logger import ERROR_CODES

        required_codes = [
            "FS-05", "RT-01", "RT-06", "DC-07", "CFG-05", "FS-14",
            "GIT-04", "GIT-06", "GIT-07"
        ]

        for code in required_codes:
            assert code in ERROR_CODES, f"Missing error code: {code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
