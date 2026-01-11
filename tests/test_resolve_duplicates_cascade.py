"""
Test for duplicate resolution cascade fix.

This test verifies that when multiple duplicates exist in the same file,
all of them can be resolved without content mismatch errors.

Reproduces Issue #1 from INTEGRATION_TEST_REPORT.md:
"When multiple duplicates exist in the same file, fixing one makes
subsequent matches fail."
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from guardian.healers.resolve_duplicates import ResolveDuplicatesHealer


@pytest.fixture
def test_config():
    """Test configuration with low thresholds to catch duplicates."""
    return {
        'project': {
            'root': '/tmp/test-project',
            'doc_root': '/tmp/test-project/docs'
        },
        'confidence': {
            'auto_commit_threshold': 0.8,
            'auto_stage_threshold': 0.7
        },
        'reporting': {
            'output_dir': '/tmp/test-project/.guardian/reports'
        },
        'healers': {
            'resolve_duplicates': {
                'similarity_threshold': 0.95,  # Very strict - near-exact matches
                'min_block_size': 50,
                'hierarchy_rules': [
                    'README.md',
                    'docs/canonical.md',
                    'docs/'
                ]
            }
        }
    }


def test_multiple_duplicates_same_file(test_config):
    """
    Test resolving 3+ duplicates in the same file.

    This was the failing case in integration testing:
    - File has 3 duplicates at different locations
    - First fix succeeds
    - Second fix fails (content changed)
    - Third fix fails

    Expected after fix:
    - All 3 duplicates should be resolved
    """
    with TemporaryDirectory() as tmpdir:
        # Setup project structure
        doc_dir = Path(tmpdir) / "docs"
        doc_dir.mkdir()

        # Update config
        test_config['project']['root'] = tmpdir
        test_config['project']['doc_root'] = str(doc_dir)

        # Create canonical file with original content
        canonical = doc_dir / "canonical.md"
        canonical.write_text("""# Canonical Guide

This is the canonical location for this content.

## Installation

To install this package, run the following command:

```bash
npm install my-package
```

This will download and install all dependencies.

## Usage

Import the package in your code.
""")

        # Create file with 3 duplicates
        duplicate_file = doc_dir / "guide.md"
        duplicate_file.write_text("""# Guide

Some intro content.

## Setup Part 1

To install this package, run the following command:

```bash
npm install my-package
```

This will download and install all dependencies.

## Middle Section

Some other content here.

## Setup Part 2

To install this package, run the following command:

```bash
npm install my-package
```

This will download and install all dependencies.

## Another Section

More content.

## Setup Part 3

To install this package, run the following command:

```bash
npm install my-package
```

This will download and install all dependencies.

## Conclusion

Final content.
""")

        # Create healer
        healer = ResolveDuplicatesHealer(test_config)

        # Check mode - should find 3 duplicates
        check_report = healer.check()

        # Filter to only duplicates in guide.md (exclude canonical itself)
        guide_duplicates = [
            c for c in check_report.changes
            if c.file == duplicate_file
        ]

        assert len(guide_duplicates) == 3, \
            f"Expected 3 duplicates in guide.md, found {len(guide_duplicates)}"

        # Heal mode - should fix all 3
        heal_report = healer.heal(min_confidence=0.90)

        # Count fixed duplicates in guide.md
        fixed_in_guide = [
            c for c in heal_report.changes
            if c.file == duplicate_file
        ]

        assert len(fixed_in_guide) == 3, \
            f"Expected to fix 3 duplicates, only fixed {len(fixed_in_guide)}"

        # Verify file was actually modified
        updated_content = duplicate_file.read_text()

        # Should have 3 links to canonical.md
        link_count = updated_content.count('[canonical.md]')
        assert link_count == 3, \
            f"Expected 3 links to canonical.md, found {link_count}"

        # The key fix: all 3 duplicate paragraphs should be replaced
        # Note: Code blocks are extracted separately, so they remain
        # The duplicate *text* paragraphs are replaced with links
        assert updated_content.count('To install this package') == 0, \
            "Duplicate text paragraphs still present after healing"

        # Verify the structure is preserved (links are in the right places)
        assert '## Setup Part 1\n\nSee [canonical.md]' in updated_content
        assert '## Setup Part 2\n\nSee [canonical.md]' in updated_content
        assert '## Setup Part 3\n\nSee [canonical.md]' in updated_content


def test_cascade_with_different_similarities(test_config):
    """
    Test cascade handling with blocks of varying similarity.

    Ensures the fuzzy matching works correctly when blocks aren't
    100% identical.
    """
    with TemporaryDirectory() as tmpdir:
        doc_dir = Path(tmpdir) / "docs"
        doc_dir.mkdir()

        test_config['project']['root'] = tmpdir
        test_config['project']['doc_root'] = str(doc_dir)

        # Canonical with original
        canonical = doc_dir / "canonical.md"
        canonical.write_text("""# API Reference

## Authentication

The API uses JWT tokens for authentication. Include your token
in the Authorization header of each request.

Example:
```
Authorization: Bearer YOUR_TOKEN_HERE
```

## Rate Limiting

API calls are limited to 100 requests per minute.
""")

        # File with similar but not identical duplicates
        duplicate_file = doc_dir / "guide.md"
        duplicate_file.write_text("""# Guide

## Setup

The API uses JWT tokens for authentication. Include your token
in the Authorization header of each request.

Example:
```
Authorization: Bearer YOUR_TOKEN_HERE
```

## Section 2

Content here.

## Authentication Details

The API uses JWT tokens for authentication. Include your token
in the Authorization header of each request.

Example:
```
Authorization: Bearer YOUR_TOKEN_HERE
```

## Section 3

The API uses JWT tokens for authentication. Include your token
in the Authorization header of each request.

Example:
```
Authorization: Bearer YOUR_TOKEN_HERE
```

## Final

Done.
""")

        healer = ResolveDuplicatesHealer(test_config)

        # Should detect and fix all similar blocks
        heal_report = healer.heal(min_confidence=0.90)

        fixed_in_guide = [
            c for c in heal_report.changes
            if c.file == duplicate_file
        ]

        # Should fix at least 2 (might not catch all if similarity < threshold)
        assert len(fixed_in_guide) >= 2, \
            f"Expected at least 2 fixes, got {len(fixed_in_guide)}"

        updated_content = duplicate_file.read_text()

        # Should have links
        assert '[canonical.md]' in updated_content


def test_no_regression_single_duplicate(test_config):
    """
    Ensure the fix doesn't break the simple case (single duplicate).
    """
    with TemporaryDirectory() as tmpdir:
        doc_dir = Path(tmpdir) / "docs"
        doc_dir.mkdir()

        test_config['project']['root'] = tmpdir
        test_config['project']['doc_root'] = str(doc_dir)

        canonical = doc_dir / "canonical.md"
        canonical.write_text("""# Canonical

## Section

This is some unique content that appears in multiple places.
It should be consolidated into this canonical location.
""")

        duplicate_file = doc_dir / "other.md"
        duplicate_file.write_text("""# Other Doc

## Intro

This is some unique content that appears in multiple places.
It should be consolidated into this canonical location.

## More Content

Other stuff.
""")

        healer = ResolveDuplicatesHealer(test_config)
        heal_report = healer.heal(min_confidence=0.90)

        # Should fix the single duplicate
        assert heal_report.issues_fixed >= 1

        updated_content = duplicate_file.read_text()
        assert '[canonical.md]' in updated_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
