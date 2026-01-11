"""
Integration tests for sync_canonical healer.

Tests JSON/YAML/TOML parsing, template rendering, confidence scoring,
and file sync operations.
"""

import json
import tempfile
from pathlib import Path

import pytest

from guardian.healers.sync_canonical import (
    CanonicalLoader,
    ChangeDetector,
    ConfidenceCalculator,
    SyncTarget,
    SyncCanonicalHealer,
)


class TestCanonicalLoader:
    """Test canonical source file loading."""

    def test_load_json(self):
        """Test loading JSON source file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_data = {"metadata": {"fan_types": ["AXIAL", "CENTRIFUGAL"]}}
            json.dump(test_data, f)
            json_path = Path(f.name)

        try:
            loader = CanonicalLoader(json_path, 'json')
            data = loader.load()

            assert data == test_data
            assert data['metadata']['fan_types'] == ["AXIAL", "CENTRIFUGAL"]
        finally:
            json_path.unlink()

    def test_get_nested_value(self):
        """Test nested value retrieval."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            test_data = {"level1": {"level2": {"level3": "value"}}}
            json.dump(test_data, f)
            json_path = Path(f.name)

        try:
            loader = CanonicalLoader(json_path, 'json')

            # Valid path
            assert loader.get_nested_value('level1.level2.level3') == 'value'

            # Partial path
            assert loader.get_nested_value('level1.level2') == {"level3": "value"}

            # Invalid path returns default
            assert loader.get_nested_value('invalid.path', default='fallback') == 'fallback'
        finally:
            json_path.unlink()

    def test_load_yaml(self):
        """Test loading YAML source file (requires PyYAML)."""
        pytest.importorskip("yaml")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("metadata:\n  fan_types:\n    - AXIAL\n    - CENTRIFUGAL\n")
            yaml_path = Path(f.name)

        try:
            loader = CanonicalLoader(yaml_path, 'yaml')
            data = loader.load()

            assert data['metadata']['fan_types'] == ["AXIAL", "CENTRIFUGAL"]
        finally:
            yaml_path.unlink()


class TestConfidenceCalculator:
    """Test confidence scoring."""

    def test_calculate_full_replace(self):
        """Test confidence for full file replacement."""
        target = SyncTarget(
            file_path=Path("test.md"),
            template_name="test.j2",
            sections=["all"],
            full_replace=True
        )

        old_content = "# Old Header\nOld content"
        new_content = "# New Header\nNew content"

        calc = ConfidenceCalculator()
        confidence = calc.calculate(target, old_content, new_content)

        # Should have high confidence (full_replace + no manual edits)
        assert confidence >= 0.8

    def test_calculate_with_sync_markers(self):
        """Test confidence for partial replacement with sync markers."""
        target = SyncTarget(
            file_path=Path("test.md"),
            template_name="test.j2",
            sections=["section1"],
            section_pattern="<!-- SYNC_START -->.*?<!-- SYNC_END -->"
        )

        old_content = """
# Header
<!-- SYNC_START -->
Old synced content
<!-- SYNC_END -->
Manual content
"""

        new_content = """
# Header
<!-- SYNC_START -->
New synced content
<!-- SYNC_END -->
Manual content
"""

        calc = ConfidenceCalculator()
        confidence = calc.calculate(target, old_content, new_content)

        # Should have high confidence (sync markers present)
        assert confidence >= 0.9

    def test_has_manual_edits(self):
        """Test manual edit detection."""
        calc = ConfidenceCalculator()

        # No manual edits
        assert calc.has_manual_edits("Normal content") is False

        # Has manual edit marker
        assert calc.has_manual_edits("# MANUAL EDIT\nContent") is True
        assert calc.has_manual_edits("# DO NOT AUTO-SYNC\nContent") is True
        assert calc.has_manual_edits("<!-- MANUAL -->\nContent") is True


class TestSyncCanonicalHealer:
    """Test SyncCanonicalHealer end-to-end."""

    def test_check_mode(self):
        """Test check mode (preview changes without applying)."""
        # Create temporary project structure
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create canonical source
            source_file = project_root / "canonical.json"
            source_file.write_text(json.dumps({
                "fan_types": ["AXIAL", "CENTRIFUGAL"],
                "model_codes": ["D53", "BC"]
            }))

            # Create template directory and template
            templates_dir = project_root / "templates"
            templates_dir.mkdir()

            template_file = templates_dir / "reference.md.j2"
            template_file.write_text("""
# Reference

Fan types: {{ data.fan_types | join(', ') }}
Model codes: {{ data.model_codes | join(', ') }}
""")

            # Create target file
            target_file = project_root / "docs" / "reference.md"
            target_file.parent.mkdir()
            target_file.write_text("# Reference\n\nOld content")

            # Configure healer
            config = {
                'project': {
                    'root': str(project_root),
                    'doc_root': str(project_root / "docs")
                },
                'confidence': {
                    'auto_commit_threshold': 0.90,
                    'auto_stage_threshold': 0.85
                },
                'reporting': {
                    'output_dir': str(project_root / "reports")
                },
                'healers': {
                    'sync_canonical': {
                        'source_file': 'canonical.json',
                        'source_format': 'json',
                        'templates_dir': str(templates_dir),
                        'target_patterns': [
                            {
                                'file': 'docs/reference.md',
                                'template': 'reference.md.j2',
                                'sections': ['all'],
                                'full_replace': True
                            }
                        ]
                    }
                }
            }

            healer = SyncCanonicalHealer(config)
            report = healer.check()

            # Should find 1 file needing sync
            assert report.issues_found == 1
            assert report.mode == "check"
            assert len(report.changes) == 1

            # Change should reference target file
            change = report.changes[0]
            assert change.file == target_file
            assert "AXIAL, CENTRIFUGAL" in change.new_content
            assert "D53, BC" in change.new_content

    def test_heal_mode(self):
        """Test heal mode (apply changes)."""
        # Similar setup to test_check_mode
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            source_file = project_root / "canonical.json"
            source_file.write_text(json.dumps({"version": "2.0"}))

            templates_dir = project_root / "templates"
            templates_dir.mkdir()

            template_file = templates_dir / "version.txt.j2"
            template_file.write_text("Version: {{ data.version }}")

            target_file = project_root / "VERSION.txt"
            target_file.write_text("Version: 1.0")

            config = {
                'project': {
                    'root': str(project_root),
                    'doc_root': str(project_root)
                },
                'confidence': {
                    'auto_commit_threshold': 0.90,
                    'auto_stage_threshold': 0.85
                },
                'reporting': {
                    'output_dir': str(project_root / "reports")
                },
                'healers': {
                    'sync_canonical': {
                        'source_file': 'canonical.json',
                        'source_format': 'json',
                        'templates_dir': str(templates_dir),
                        'backup_dir': str(project_root / "backups"),
                        'target_patterns': [
                            {
                                'file': 'VERSION.txt',
                                'template': 'version.txt.j2',
                                'sections': ['all'],
                                'full_replace': True
                            }
                        ]
                    }
                }
            }

            healer = SyncCanonicalHealer(config)

            # Apply changes
            report = healer.heal(min_confidence=0.5)  # Lower threshold for test

            # Should have applied 1 fix
            assert report.issues_fixed >= 1
            assert report.mode == "heal"

            # Target file should be updated
            updated_content = target_file.read_text()
            assert "Version: 2.0" in updated_content

            # Backup should exist
            backup_dir = project_root / "backups"
            backups = list(backup_dir.glob("VERSION.txt.*.bak"))
            assert len(backups) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
