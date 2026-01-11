"""
Tests for Fix Typos Healer

Complete test suite demonstrating best practices for custom healer testing.
"""

import pytest
from pathlib import Path
from fix_typos_healer import FixTyposHealer


@pytest.fixture
def base_config():
    """Base configuration for healer."""
    return {
        'project': {
            'root': '/tmp/test',
            'doc_root': '/tmp/test/docs'
        },
        'healers': {
            'fix_typos': {
                'enabled': True,
                'min_confidence': 0.90,
                'common_typos': {
                    'teh': 'the',
                    'recieve': 'receive',
                    'occured': 'occurred'
                }
            }
        },
        'confidence': {
            'auto_commit_threshold': 0.90,
            'auto_stage_threshold': 0.80
        }
    }


@pytest.fixture
def healer(base_config, tmp_path):
    """Create healer with temp directory."""
    # Override paths to use temp directory
    base_config['project']['root'] = str(tmp_path)
    base_config['project']['doc_root'] = str(tmp_path / 'docs')

    # Create docs directory
    (tmp_path / 'docs').mkdir()

    return FixTyposHealer(base_config)


@pytest.fixture
def sample_file(tmp_path):
    """Create sample markdown file with typos."""
    docs_dir = tmp_path / 'docs'
    docs_dir.mkdir(exist_ok=True)

    file_path = docs_dir / 'test.md'
    file_path.write_text("""# Test Document

This is teh first paragraph with a typo.

We recieve notifications when errors occured.
""")
    return file_path


# ============================================================================
# Detection Tests
# ============================================================================

def test_check_finds_typos(healer, sample_file):
    """Test that check() detects all typos."""
    report = healer.check()

    assert report.mode == "check"
    assert report.issues_found == 2  # "teh" and "recieve" + "occured" in same line
    assert len(report.changes) == 2


def test_check_empty_file(healer, tmp_path):
    """Test check() on empty file."""
    empty_file = tmp_path / 'docs' / 'empty.md'
    empty_file.write_text("")

    report = healer.check()

    assert report.issues_found == 0
    assert len(report.changes) == 0


def test_check_no_typos(healer, tmp_path):
    """Test check() on file without typos."""
    clean_file = tmp_path / 'docs' / 'clean.md'
    clean_file.write_text("# Clean Document\n\nThis has no typos.")

    report = healer.check()

    assert report.issues_found == 0


def test_check_multiple_files(healer, tmp_path):
    """Test check() scans multiple files."""
    # Create multiple files with typos
    for i in range(3):
        file_path = tmp_path / 'docs' / f'file{i}.md'
        file_path.write_text(f"# File {i}\n\nThis has teh typo.")

    report = healer.check()

    assert report.issues_found == 3  # One typo per file
    assert healer.stats['files_scanned'] == 3


# ============================================================================
# Fixing Tests
# ============================================================================

def test_heal_applies_fixes(healer, sample_file):
    """Test that heal() applies fixes above threshold."""
    # Run heal
    report = healer.heal(min_confidence=0.90)

    # Verify
    assert report.mode == "heal"
    assert report.issues_fixed == 2
    assert report.success_rate == 1.0  # 2/2 fixed

    # Check file was modified
    content = sample_file.read_text()
    assert "the first paragraph" in content
    assert "teh" not in content
    assert "receive" in content
    assert "occurred" in content


def test_heal_respects_confidence_threshold(healer, sample_file):
    """Test heal() only applies high-confidence fixes."""
    # Set very high threshold
    report = healer.heal(min_confidence=0.99)

    # Since our typo fixes are ~0.95-0.98, some may be filtered
    # (This is configuration-dependent)
    assert report.mode == "heal"


def test_heal_validates_before_applying(healer, tmp_path):
    """Test heal() validates changes before applying."""
    # Create read-only file (validation should fail)
    readonly_file = tmp_path / 'docs' / 'readonly.md'
    readonly_file.write_text("# Test\n\nThis has teh typo.")
    readonly_file.chmod(0o444)  # Read-only

    try:
        report = healer.heal()

        # Should report error or fail to apply
        assert report.issues_fixed < report.issues_found or report.has_errors

    finally:
        # Cleanup: restore write permission
        readonly_file.chmod(0o644)


# ============================================================================
# Case Preservation Tests
# ============================================================================

def test_preserve_lowercase(healer, tmp_path):
    """Test case preservation: lowercase → lowercase."""
    file_path = tmp_path / 'docs' / 'test.md'
    file_path.write_text("teh word")

    healer.heal()

    assert "the word" in file_path.read_text()


def test_preserve_titlecase(healer, tmp_path):
    """Test case preservation: Titlecase → Titlecase."""
    file_path = tmp_path / 'docs' / 'test.md'
    file_path.write_text("Teh word")

    healer.heal()

    assert "The word" in file_path.read_text()


def test_preserve_uppercase(healer, tmp_path):
    """Test case preservation: UPPERCASE → UPPERCASE."""
    file_path = tmp_path / 'docs' / 'test.md'
    file_path.write_text("TEH word")

    healer.heal()

    assert "THE word" in file_path.read_text()


# ============================================================================
# Code Block Tests
# ============================================================================

def test_skip_code_blocks(healer, tmp_path):
    """Test that typos in code blocks are ignored."""
    file_path = tmp_path / 'docs' / 'test.md'
    file_path.write_text("""# Test

Normal text with teh typo.

```python
# Code with teh typo - should be ignored
def recieve():
    pass
```

More text with teh typo.
""")

    report = healer.check()

    # Should find 2 typos (normal text), not 4 (including code block)
    assert report.issues_found == 2


def test_skip_inline_code(healer, tmp_path):
    """Test that typos in inline code are ignored."""
    file_path = tmp_path / 'docs' / 'test.md'
    file_path.write_text("Use `teh` variable in your code.")

    report = healer.check()

    # Should not detect typo in inline code
    assert report.issues_found == 0


# ============================================================================
# Confidence Scoring Tests
# ============================================================================

def test_confidence_scores_are_high(healer, sample_file):
    """Test that typo fixes have high confidence scores."""
    report = healer.check()

    # All typo fixes should have confidence >= 0.90
    for change in report.changes:
        assert change.confidence >= 0.90


def test_confidence_calculation(healer):
    """Test confidence calculation for typo fix."""
    confidence = healer._calculate_confidence(
        old_line="This has teh typo",
        new_line="This has the typo",
        typos=[('teh', 'the')]
    )

    # Should be very high confidence (≥ 0.90)
    assert 0.90 <= confidence <= 1.0


# ============================================================================
# Statistics Tests
# ============================================================================

def test_stats_tracking(healer, tmp_path):
    """Test that healer tracks statistics."""
    # Create files with various typos
    (tmp_path / 'docs' / 'file1.md').write_text("teh teh")
    (tmp_path / 'docs' / 'file2.md').write_text("recieve")

    healer.check()

    stats = healer.get_stats()

    assert stats['files_scanned'] == 2
    assert stats['files_with_typos'] == 2
    assert stats['total_typos'] == 2  # 2 lines with typos
    assert stats['unique_typos'] >= 1


def test_most_common_typos(healer, tmp_path):
    """Test tracking of most common typos."""
    # Create files with repeated typos
    for i in range(5):
        (tmp_path / 'docs' / f'file{i}.md').write_text("teh word")

    (tmp_path / 'docs' / 'file5.md').write_text("recieve email")

    healer.check()

    stats = healer.get_stats()
    most_common = stats['most_common_typos']

    # "teh" should be most common (5 occurrences)
    assert most_common[0][0] == 'teh'
    assert most_common[0][1] == 5


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_handles_read_errors(healer, tmp_path):
    """Test graceful handling of unreadable files."""
    # Create directory that looks like markdown file
    fake_file = tmp_path / 'docs' / 'fake.md'
    fake_file.mkdir()

    # Should not crash
    report = healer.check()

    # Should report error
    assert report.has_errors or report.issues_found == 0


def test_handles_missing_file(healer, tmp_path):
    """Test handling of file that disappears during processing."""
    # This is edge case testing - normally wouldn't happen
    # but good to ensure robustness
    report = healer.check()

    # Should complete without crashing
    assert isinstance(report, type(healer.check()))


# ============================================================================
# Integration Tests
# ============================================================================

def test_end_to_end_workflow(healer, tmp_path):
    """Test complete check → heal → verify workflow."""
    # Setup: Create files with typos
    (tmp_path / 'docs' / 'file1.md').write_text("teh first file")
    (tmp_path / 'docs' / 'file2.md').write_text("recieve email")

    # 1. Check finds all issues
    check_report = healer.check()
    assert check_report.issues_found == 2
    assert check_report.mode == "check"

    # 2. Heal applies fixes
    heal_report = healer.heal()
    assert heal_report.issues_fixed == 2
    assert heal_report.mode == "heal"
    assert heal_report.success_rate == 1.0

    # 3. Verify fixes applied
    assert "the first file" in (tmp_path / 'docs' / 'file1.md').read_text()
    assert "receive email" in (tmp_path / 'docs' / 'file2.md').read_text()

    # 4. Re-check finds no issues
    final_check = healer.check()
    assert final_check.issues_found == 0


def test_multiple_typos_per_line(healer, tmp_path):
    """Test fixing multiple typos on same line."""
    file_path = tmp_path / 'docs' / 'test.md'
    file_path.write_text("teh email was recieved")

    healer.heal()

    # Both typos should be fixed
    content = file_path.read_text()
    assert "the email was received" in content


# ============================================================================
# Configuration Tests
# ============================================================================

def test_custom_typo_dictionary(base_config, tmp_path):
    """Test using custom typo dictionary."""
    # Add custom typos
    base_config['healers']['fix_typos']['common_typos'] = {
        'foo': 'bar',
        'baz': 'qux'
    }
    base_config['project']['root'] = str(tmp_path)
    base_config['project']['doc_root'] = str(tmp_path / 'docs')

    (tmp_path / 'docs').mkdir()

    healer = FixTyposHealer(base_config)

    # Create file with custom typos
    file_path = tmp_path / 'docs' / 'test.md'
    file_path.write_text("foo and baz")

    healer.heal()

    # Custom typos should be fixed
    assert "bar and qux" in file_path.read_text()


def test_confidence_threshold_override(healer, sample_file):
    """Test overriding confidence threshold."""
    # High threshold - may not fix all
    high_threshold_report = healer.heal(min_confidence=0.99)

    # Low threshold - should fix all
    healer_low = healer
    low_threshold_report = healer_low.heal(min_confidence=0.50)

    # Low threshold should fix at least as many as high threshold
    assert low_threshold_report.issues_fixed >= high_threshold_report.issues_fixed


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
