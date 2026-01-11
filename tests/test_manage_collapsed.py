"""
Tests for ManageCollapsedHealer.

Verifies:
1. HTML parsing works
2. Hint generation strategies work
3. Keyword extraction works
4. No TCF-specific paths
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from guardian.healers.manage_collapsed import (
    ManageCollapsedHealer,
    CollapsedSectionExtractor,
    ExpandHintGenerator,
    SearchIndexChecker,
    UnusedSectionDetector,
    CollapsedSection
)


@pytest.fixture
def sample_markdown():
    """Sample markdown with collapsed sections."""
    return """
# Documentation

Some intro text.

<details>
<summary>Section 1</summary>

This is the first collapsed section with some content.

```python
def hello():
    print("world")
```

- Item 1
- Item 2
- Item 3

</details>

Normal content here.

<details>
<summary>Long Section (Expand to see: 15 command examples)</summary>

This section already has a good hint.

```bash
npm install
npm test
npm build
```

</details>

<details>
<summary>Generic Section</summary>

This is a very long section with lots of content.
""" + "\n" * 600 + """
Lots of lines here...

</details>
"""


@pytest.fixture
def test_config():
    """Test configuration."""
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
            'manage_collapsed': {
                'hint_strategy': 'summary',
                'track_usage': False,
                'long_section_threshold': 500,
                'missing_keywords_threshold': 0.5
            }
        }
    }


def test_html_parsing():
    """Test HTML <details> parsing."""
    extractor = CollapsedSectionExtractor()

    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.md"
        test_file.write_text("""
<details>
<summary>Test Section</summary>
Content here
</details>
""")

        sections = extractor.extract(test_file)

        assert len(sections) == 1
        assert sections[0].title == "Test Section"
        assert "Content here" in sections[0].content


def test_keyword_extraction():
    """Test keyword extraction from content."""
    extractor = CollapsedSectionExtractor()

    keywords = extractor._extract_keywords("""
    This is a test document about Python programming.
    It includes code examples and configuration details.
    """)

    # Should extract meaningful words
    assert 'python' in keywords
    assert 'programming' in keywords
    assert 'code' in keywords
    assert 'configuration' in keywords

    # Should exclude stopwords
    assert 'the' not in keywords
    assert 'and' not in keywords


def test_hint_generation_summary_strategy():
    """Test hint generation with 'summary' strategy."""
    generator = ExpandHintGenerator(strategy='summary')

    section = CollapsedSection(
        file=Path("test.md"),
        title="Test",
        summary="Test",
        content="""
Some intro.

```python
print("hello")
```

```bash
npm install
```

- Item 1
- Item 2
- Item 3
""",
        start_line=1,
        end_line=10,
        keywords=set()
    )

    hint = generator.generate_hint(section)

    # Should mention code blocks and items
    assert 'code example' in hint or 'command' in hint
    assert '2' in hint  # 2 code blocks
    assert '3' in hint or 'item' in hint  # 3 bullet points


def test_hint_generation_first_sentence_strategy():
    """Test hint generation with 'first_sentence' strategy."""
    generator = ExpandHintGenerator(strategy='first_sentence')

    section = CollapsedSection(
        file=Path("test.md"),
        title="Test",
        summary="Test",
        content="This is a short intro sentence. More content follows.",
        start_line=1,
        end_line=5,
        keywords=set()
    )

    hint = generator.generate_hint(section)

    assert "short intro sentence" in hint


def test_unused_detection():
    """Test detection of unused/long sections."""
    detector = UnusedSectionDetector(long_section_threshold=500)

    # Short section - should not flag
    short_section = CollapsedSection(
        file=Path("test.md"),
        title="Short",
        summary="Short",
        content="Small content\n" * 10,
        start_line=1,
        end_line=11,
        keywords=set()
    )

    # Long section - should flag
    long_section = CollapsedSection(
        file=Path("test.md"),
        title="Long",
        summary="Long",
        content="Line\n" * 600,
        start_line=1,
        end_line=601,
        keywords=set()
    )

    issues = detector.detect_unused([short_section, long_section])

    assert len(issues) == 1
    assert issues[0]['section'].title == "Long"
    assert issues[0]['issue_type'] == 'unused'


def test_healer_check(test_config, sample_markdown):
    """Test healer check mode."""
    with TemporaryDirectory() as tmpdir:
        # Setup test directory
        doc_dir = Path(tmpdir) / "docs"
        doc_dir.mkdir()

        test_file = doc_dir / "test.md"
        test_file.write_text(sample_markdown)

        # Update config paths
        test_config['project']['root'] = tmpdir
        test_config['project']['doc_root'] = str(doc_dir)

        # Create healer
        healer = ManageCollapsedHealer(test_config)

        # Run check
        report = healer.check()

        assert report.mode == "check"
        assert report.issues_found > 0  # Should find poor hints

        # Should have changes proposed
        assert len(report.changes) > 0

        # Should NOT have applied changes
        assert report.issues_fixed == 0


def test_healer_heal(test_config, sample_markdown):
    """Test healer heal mode."""
    with TemporaryDirectory() as tmpdir:
        # Setup test directory
        doc_dir = Path(tmpdir) / "docs"
        doc_dir.mkdir()

        test_file = doc_dir / "test.md"
        test_file.write_text(sample_markdown)

        # Update config paths
        test_config['project']['root'] = tmpdir
        test_config['project']['doc_root'] = str(doc_dir)

        # Create healer
        healer = ManageCollapsedHealer(test_config)

        # Run heal
        report = healer.heal(min_confidence=0.7)

        assert report.mode == "heal"
        assert report.issues_found > 0
        assert report.issues_fixed >= 0  # May fix some issues

        # If fixes were applied, verify file changed
        if report.issues_fixed > 0:
            updated_content = test_file.read_text()
            assert updated_content != sample_markdown


def test_no_tcf_specific_paths():
    """Verify no TCF-specific hardcoded paths."""
    from guardian.healers import manage_collapsed
    import inspect

    source = inspect.getsource(manage_collapsed)

    # Should not contain TCF-specific paths
    assert '/home/moroshek/TCF' not in source
    assert 'CLAUDE.md' not in source
    assert 'PROJECT_ROOT' not in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
