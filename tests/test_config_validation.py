"""
Test suite for configuration validation.

Tests all 8 CRITICAL config validation fixes:
1. Path traversal prevention
2. Numeric range validation (0.0-1.0)
3. Type checking enforcement
4. Resource limits
5. List vs string handling
6. Path existence validation
7. Regex pattern validation
8. Error message clarity
"""

import pytest
import tempfile
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from guardian.core.config_validator import (
    ConfigError,
    ConfigValidationError,
    ValidationResult,
    validate_config_schema,
    validate_path_traversal,
    validate_path_exists,
    validate_threshold,
    validate_positive_int,
    validate_regex_pattern,
    ensure_list,
    safe_read_file,
    validate_and_load_config,
    load_config_strict,
    MAX_FILE_SIZE,
    MAX_PATTERN_LENGTH,
    MAX_ARRAY_SIZE,
    MAX_NESTING_DEPTH,
)


class TestPathTraversalPrevention:
    """Test CRITICAL fix #1: Path traversal prevention."""

    def test_path_within_root_allowed(self, tmp_path):
        """Paths within project root should be allowed."""
        subdir = tmp_path / "docs"
        subdir.mkdir()
        result = validate_path_traversal(subdir, tmp_path, "test.path")
        assert result == subdir.resolve()

    def test_path_traversal_blocked(self, tmp_path):
        """Paths escaping project root should be rejected."""
        malicious_path = tmp_path / ".." / ".." / "etc"
        with pytest.raises(ConfigError) as exc_info:
            validate_path_traversal(malicious_path, tmp_path, "test.path")
        assert "escapes project root" in str(exc_info.value)

    def test_absolute_path_outside_root_blocked(self, tmp_path):
        """Absolute paths outside root should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_path_traversal(Path("/etc"), tmp_path, "test.path")
        assert "escapes project root" in str(exc_info.value)


class TestNumericRangeValidation:
    """Test CRITICAL fix #2: Numeric range validation."""

    def test_valid_threshold_accepted(self):
        """Valid thresholds (0.0-1.0) should be accepted."""
        assert validate_threshold(0.0, "test") == 0.0
        assert validate_threshold(0.5, "test") == 0.5
        assert validate_threshold(1.0, "test") == 1.0
        assert validate_threshold(0.95, "test") == 0.95

    def test_threshold_above_one_rejected(self):
        """Thresholds > 1.0 should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_threshold(1.5, "confidence.auto_commit")
        assert "too high" in str(exc_info.value).lower() or "maximum" in str(exc_info.value).lower()

    def test_negative_threshold_rejected(self):
        """Negative thresholds should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_threshold(-0.5, "confidence.auto_commit")
        assert "too low" in str(exc_info.value).lower() or "minimum" in str(exc_info.value).lower()

    def test_nan_rejected(self):
        """NaN values should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_threshold(float('nan'), "test")
        assert "nan" in str(exc_info.value).lower()

    def test_infinity_rejected(self):
        """Infinite values should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_threshold(float('inf'), "test")
        assert "infinite" in str(exc_info.value).lower()


class TestTypeCheckingEnforcement:
    """Test CRITICAL fix #3: Type checking enforcement."""

    def test_string_threshold_rejected(self):
        """String values for thresholds should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_threshold("0.9", "test")
        assert "string" in str(exc_info.value).lower() or "number" in str(exc_info.value).lower()

    def test_none_threshold_rejected(self):
        """None values for thresholds should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_threshold(None, "test")
        assert "null" in str(exc_info.value).lower() or "none" in str(exc_info.value).lower()

    def test_int_as_threshold_accepted(self):
        """Integer values should be converted to float."""
        assert validate_threshold(1, "test") == 1.0
        assert isinstance(validate_threshold(1, "test"), float)

    def test_positive_int_rejects_float(self):
        """Positive int validator should reject floats."""
        with pytest.raises(ConfigError) as exc_info:
            validate_positive_int(1.5, "test")
        assert "Must be an integer" in str(exc_info.value)

    def test_positive_int_rejects_bool(self):
        """Positive int validator should reject booleans."""
        with pytest.raises(ConfigError) as exc_info:
            validate_positive_int(True, "test")
        assert "Must be an integer" in str(exc_info.value)


class TestResourceLimits:
    """Test CRITICAL fix #4: Resource limits."""

    def test_pattern_length_limit(self):
        """Patterns exceeding max length should be rejected."""
        long_pattern = "a" * (MAX_PATTERN_LENGTH + 1)
        with pytest.raises(ConfigError) as exc_info:
            validate_regex_pattern(long_pattern, "test")
        assert "length" in str(exc_info.value).lower() or "exceeds" in str(exc_info.value).lower()

    def test_file_size_limit(self, tmp_path):
        """Files exceeding size limit should be rejected."""
        large_file = tmp_path / "large.txt"
        # Create a file that appears larger than MAX_FILE_SIZE
        # by mocking or using a smaller test limit
        large_file.write_text("x")  # Create file first
        with pytest.raises(ValueError) as exc_info:
            safe_read_file(large_file, max_size=0)  # Use 0 as test limit
        assert "File too large" in str(exc_info.value)


class TestListVsStringHandling:
    """Test CRITICAL fix #5: List vs string handling."""

    def test_string_converted_to_list(self):
        """String values should be converted to single-item lists."""
        result = ensure_list("single_item", "test")
        assert result == ["single_item"]

    def test_list_passed_through(self):
        """List values should be passed through unchanged."""
        result = ensure_list(["a", "b", "c"], "test")
        assert result == ["a", "b", "c"]

    def test_none_returns_empty_list(self):
        """None should return empty list."""
        result = ensure_list(None, "test")
        assert result == []

    def test_dict_rejected(self):
        """Dict values should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            ensure_list({"key": "value"}, "test")
        assert "Expected list" in str(exc_info.value)


class TestPathExistenceValidation:
    """Test CRITICAL fix #6: Path existence validation."""

    def test_existing_path_accepted(self, tmp_path):
        """Existing paths should be accepted."""
        result = validate_path_exists(tmp_path, "test")
        assert result == tmp_path.resolve()

    def test_nonexistent_path_rejected(self):
        """Non-existent paths should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_path_exists(Path("/nonexistent/path"), "test")
        assert "does not exist" in str(exc_info.value)

    def test_must_be_dir_enforced(self, tmp_path):
        """must_be_dir should reject files."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        with pytest.raises(ConfigError) as exc_info:
            validate_path_exists(test_file, "test", must_be_dir=True)
        assert "must be a directory" in str(exc_info.value)

    def test_must_be_file_enforced(self, tmp_path):
        """must_be_file should reject directories."""
        with pytest.raises(ConfigError) as exc_info:
            validate_path_exists(tmp_path, "test", must_be_file=True)
        assert "must be a file" in str(exc_info.value)

    def test_home_expansion(self):
        """~ should be expanded to home directory."""
        home = Path.home()
        if home.exists():
            result = validate_path_exists(Path("~"), "test")
            assert result == home.resolve()


class TestRegexPatternValidation:
    """Test CRITICAL fix #7: Regex pattern validation."""

    def test_valid_pattern_accepted(self):
        """Valid regex patterns should be accepted."""
        pattern = validate_regex_pattern(r"\[([^\]]+)\]\(([^\)]+)\)", "test")
        assert isinstance(pattern, re.Pattern)

    def test_invalid_pattern_rejected(self):
        """Invalid regex syntax should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_regex_pattern("[unclosed", "test")
        assert "Invalid regex pattern" in str(exc_info.value)

    def test_redos_pattern_rejected(self):
        """ReDoS-prone patterns should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_regex_pattern(r"(.*?){10}", "test")
        assert "backtracking" in str(exc_info.value).lower() or "redos" in str(exc_info.value).lower()

    def test_nested_quantifiers_rejected(self):
        """Nested quantifiers should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_regex_pattern(r"([a-z]+)+", "test")
        # This specific pattern might not be caught, adjust if needed

    def test_non_string_pattern_rejected(self):
        """Non-string patterns should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_regex_pattern(123, "test")
        assert "must be a string" in str(exc_info.value)


class TestErrorMessageClarity:
    """Test CRITICAL fix #8: Error message clarity."""

    def test_config_error_includes_key(self):
        """ConfigError should include the config key."""
        error = ConfigError("project.root", "is missing")
        assert "project.root" in str(error)

    def test_config_error_includes_value(self):
        """ConfigError should include the invalid value."""
        error = ConfigError("threshold", "invalid", 1.5)
        assert "1.5" in str(error)

    def test_validation_errors_are_specific(self, tmp_path):
        """Validation errors should be specific and actionable."""
        config = {
            "project": {
                "root": str(tmp_path),
                "doc_root": str(tmp_path),
            },
            "confidence": {
                "auto_commit_threshold": 1.5,  # Invalid
            }
        }
        result = validate_config_schema(config)
        assert not result.is_valid
        assert any("1.0" in err for err in result.errors)


class TestFullConfigValidation:
    """Test complete config validation scenarios."""

    def test_valid_minimal_config(self, tmp_path):
        """Minimal valid config should pass."""
        config = {
            "project": {
                "root": str(tmp_path),
                "doc_root": str(tmp_path),
            }
        }
        result = validate_config_schema(config)
        assert result.is_valid, f"Errors: {result.errors}"

    def test_missing_project_section(self):
        """Missing project section should fail."""
        config = {"healers": {}}
        result = validate_config_schema(config)
        assert not result.is_valid
        assert any("project" in err.lower() for err in result.errors)

    def test_missing_root_key(self, tmp_path):
        """Missing root key should fail."""
        config = {
            "project": {
                "doc_root": str(tmp_path),
            }
        }
        result = validate_config_schema(config)
        assert not result.is_valid
        assert any("root" in err.lower() for err in result.errors)

    def test_inverted_thresholds_warning(self, tmp_path):
        """Inverted thresholds should generate warning."""
        config = {
            "project": {
                "root": str(tmp_path),
                "doc_root": str(tmp_path),
            },
            "confidence": {
                "auto_commit_threshold": 0.7,
                "auto_stage_threshold": 0.9,  # Higher than commit
            }
        }
        result = validate_config_schema(config)
        assert len(result.warnings) > 0
        assert any("threshold" in w.lower() for w in result.warnings)

    def test_unimplemented_features_warning(self, tmp_path):
        """Unimplemented features should generate warning."""
        config = {
            "project": {
                "root": str(tmp_path),
                "doc_root": str(tmp_path),
            },
            "advanced": {
                "max_workers": 4,
                "enable_cache": True,
            }
        }
        result = validate_config_schema(config)
        assert len(result.warnings) > 0
        assert any("not yet implemented" in w.lower() for w in result.warnings)


class TestConfigValidationEdgeCases:
    """Test edge cases from CONFIG_VALIDATION_AUDIT.md (127 edge cases)."""

    # === Path Traversal Edge Cases (PT-*) ===

    def test_null_byte_in_path_rejected(self, tmp_path):
        """PT-001: Null byte in path should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_path_traversal("docs\x00/evil", tmp_path, "test.path")
        assert "null byte" in str(exc_info.value).lower()

    def test_newline_in_path_rejected(self, tmp_path):
        """PT-002: Newline in path should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_path_traversal("docs\n../etc/passwd", tmp_path, "test.path")
        assert "newline" in str(exc_info.value).lower()

    def test_home_directory_expanded(self, tmp_path):
        """PT-003: ~ should be expanded to home directory."""
        home = Path.home()
        if home.exists():
            result = validate_path_traversal("~", home, "test.path")
            assert str(result).startswith(str(home.resolve()))

    def test_double_dot_blocked_explicitly(self, tmp_path):
        """PT-004: Explicit '..' path should be blocked."""
        with pytest.raises(ConfigError) as exc_info:
            validate_path_traversal("../outside", tmp_path, "test.path")
        assert ".." in str(exc_info.value)

    # === Numeric Validation Edge Cases (NV-*) ===

    def test_string_zero_threshold_rejected(self):
        """NV-001: String "0.9" should be rejected (not silently converted)."""
        with pytest.raises(ConfigError) as exc_info:
            validate_threshold("0.9", "confidence.auto_commit_threshold")
        assert "string" in str(exc_info.value).lower()

    def test_negative_infinity_rejected(self):
        """NV-002: Negative infinity should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_threshold(float('-inf'), "test")
        assert "infinite" in str(exc_info.value).lower()

    def test_staleness_days_zero_warning(self, tmp_path):
        """NV-003: staleness_threshold_days=0 should generate warning."""
        config = {
            "project": {"root": str(tmp_path), "doc_root": str(tmp_path)},
            "healers": {
                "detect_staleness": {
                    "enabled": True,
                    "staleness_threshold_days": 0
                }
            }
        }
        result = validate_config_schema(config)
        # May generate warning or error for 0 value
        assert len(result.warnings) > 0 or len(result.errors) > 0

    # === Type Coercion Edge Cases (TC-*) ===

    def test_string_false_boolean_warning(self, tmp_path):
        """TC-005: String "false" for boolean should warn (truthy in Python)."""
        config = {
            "project": {"root": str(tmp_path), "doc_root": str(tmp_path)},
            "healers": {
                "fix_broken_links": {
                    "enabled": "false"  # String, not boolean
                }
            }
        }
        result = validate_config_schema(config)
        # Should generate a warning about string boolean
        assert len(result.warnings) > 0 or any("string" in e.lower() for e in result.errors)

    def test_list_as_string_converted(self):
        """TC-006: Single string where list expected should convert with warning."""
        result = ensure_list(".md", "file_extensions")
        assert result == [".md"]

    def test_dict_as_list_rejected(self):
        """TC-007: Dict where list expected should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            ensure_list({"ext": ".md"}, "file_extensions")
        assert "list" in str(exc_info.value).lower()

    # === Resource Limit Edge Cases (RL-*) ===

    def test_deeply_nested_config_rejected(self, tmp_path):
        """RL-001: Config exceeding max nesting depth should be rejected."""
        # Build a deeply nested dict
        nested = {"value": "test"}
        for _ in range(MAX_NESTING_DEPTH + 5):
            nested = {"nested": nested}
        config = {
            "project": {"root": str(tmp_path), "doc_root": str(tmp_path)},
            "deep": nested
        }
        result = validate_config_schema(config)
        assert not result.is_valid
        assert any("nesting" in e.lower() or "depth" in e.lower() for e in result.errors)

    def test_max_array_size_exceeded(self):
        """RL-002: Array exceeding max size should be rejected."""
        huge_list = ["item"] * (MAX_ARRAY_SIZE + 1)
        with pytest.raises(ConfigError) as exc_info:
            ensure_list(huge_list, "test")
        assert "limit" in str(exc_info.value).lower() or "exceed" in str(exc_info.value).lower()

    # === Regex Edge Cases (RX-*) ===

    def test_empty_regex_rejected(self):
        """RX-001: Empty regex pattern should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_regex_pattern("", "link_pattern")
        assert "empty" in str(exc_info.value).lower()

    def test_none_regex_rejected(self):
        """RX-002: None regex pattern should be rejected."""
        with pytest.raises(ConfigError) as exc_info:
            validate_regex_pattern(None, "link_pattern")
        assert "null" in str(exc_info.value).lower() or "none" in str(exc_info.value).lower()

    def test_unbalanced_parens_clear_error(self):
        """RX-003: Unbalanced parentheses should have clear error message."""
        with pytest.raises(ConfigError) as exc_info:
            validate_regex_pattern("(unclosed", "link_pattern")
        error_msg = str(exc_info.value).lower()
        assert "pattern" in error_msg
        # Should have position info or helpful message

    # === Healer-Specific Edge Cases (HS-*) ===

    def test_sync_canonical_requires_source_file(self, tmp_path):
        """HS-001: sync_canonical enabled requires source_file."""
        config = {
            "project": {"root": str(tmp_path), "doc_root": str(tmp_path)},
            "healers": {
                "sync_canonical": {
                    "enabled": True
                    # Missing source_file
                }
            }
        }
        result = validate_config_schema(config)
        assert not result.is_valid
        assert any("source_file" in e.lower() for e in result.errors)

    def test_manage_collapsed_invalid_strategy(self, tmp_path):
        """HS-002: Invalid hint_strategy should be rejected."""
        config = {
            "project": {"root": str(tmp_path), "doc_root": str(tmp_path)},
            "healers": {
                "manage_collapsed": {
                    "enabled": True,
                    "hint_strategy": "invalid_strategy"
                }
            }
        }
        result = validate_config_schema(config)
        assert not result.is_valid
        assert any("hint_strategy" in e.lower() for e in result.errors)

    def test_layer_definitions_nested_validation(self, tmp_path):
        """HS-003: enforce_disclosure layer_definitions should be validated."""
        config = {
            "project": {"root": str(tmp_path), "doc_root": str(tmp_path)},
            "healers": {
                "enforce_disclosure": {
                    "enabled": True,
                    "layer_definitions": {
                        "tier1": {
                            "max_lines": "not_a_number",  # Invalid
                            "allowed_depth": 3
                        }
                    }
                }
            }
        }
        result = validate_config_schema(config)
        assert not result.is_valid

    # === Error Message Quality Edge Cases (EM-*) ===

    def test_error_includes_suggestion(self):
        """EM-001: Errors should include helpful suggestions."""
        error = ConfigError("confidence.auto_commit", "Value too high", 1.5, "Decrease to at most 1.0")
        error_str = str(error)
        assert "Suggestion" in error_str or "1.0" in error_str

    def test_validation_result_raise_helper(self, tmp_path):
        """EM-002: ValidationResult.raise_if_invalid should work."""
        config = {"project": {}}  # Invalid - missing keys
        result = validate_config_schema(config)
        with pytest.raises(ConfigValidationError):
            result.raise_if_invalid()


class TestConfigFileLoading:
    """Test config file loading and validation."""

    def test_load_toml_file(self, tmp_path):
        """Should load and validate TOML files."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[project]
root = "."
doc_root = "docs/"

[confidence]
auto_commit_threshold = 0.9
''')
        (tmp_path / "docs").mkdir()

        config, result = validate_and_load_config(config_file)
        assert result.is_valid
        assert config["confidence"]["auto_commit_threshold"] == 0.9

    def test_load_yaml_file(self, tmp_path):
        """Should load and validate YAML files."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text('''
project:
  root: "."
  doc_root: "docs/"

confidence:
  auto_commit_threshold: 0.9
''')
        (tmp_path / "docs").mkdir()

        config, result = validate_and_load_config(config_file)
        assert result.is_valid
        assert config["confidence"]["auto_commit_threshold"] == 0.9

    def test_load_json_file(self, tmp_path):
        """Should load and validate JSON files."""
        import json
        config_file = tmp_path / "config.json"
        config_data = {
            "project": {"root": ".", "doc_root": "docs/"},
            "confidence": {"auto_commit_threshold": 0.9}
        }
        config_file.write_text(json.dumps(config_data))
        (tmp_path / "docs").mkdir()

        config, result = validate_and_load_config(config_file)
        assert result.is_valid

    def test_empty_config_file_rejected(self, tmp_path):
        """Empty config file should be rejected."""
        config_file = tmp_path / "empty.toml"
        config_file.write_text("")

        with pytest.raises(ValueError) as exc_info:
            validate_and_load_config(config_file)
        assert "empty" in str(exc_info.value).lower()

    def test_nonexistent_file_rejected(self, tmp_path):
        """Non-existent config file should be rejected."""
        with pytest.raises(FileNotFoundError):
            validate_and_load_config(tmp_path / "nonexistent.toml")

    def test_malformed_toml_rejected(self, tmp_path):
        """Malformed TOML should be rejected with parse error."""
        config_file = tmp_path / "bad.toml"
        config_file.write_text("this is not valid = toml = syntax [[[")

        config, result = validate_and_load_config(config_file)
        assert not result.is_valid
        assert any("parse" in e.lower() for e in result.errors)

    def test_load_strict_raises_on_error(self, tmp_path):
        """load_config_strict should raise on validation errors."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('''
[project]
# Missing required root and doc_root
name = "test"
''')

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config_strict(config_file)
        assert len(exc_info.value.errors) > 0


class TestConfigValidationIntegration:
    """Integration tests for complete config validation workflow."""

    def test_full_valid_config(self, tmp_path):
        """Complete valid configuration should pass all checks."""
        # Create directory structure
        docs = tmp_path / "docs"
        docs.mkdir()
        source = tmp_path / "data" / "source.json"
        source.parent.mkdir()
        source.write_text('{"key": "value"}')

        config = {
            "project": {
                "root": str(tmp_path),
                "doc_root": str(docs),
                "excluded_dirs": [".git", "node_modules"]
            },
            "confidence": {
                "auto_commit_threshold": 0.95,
                "auto_stage_threshold": 0.80,
                "report_only_threshold": 0.50
            },
            "healers": {
                "fix_broken_links": {
                    "enabled": True,
                    "link_pattern": r'\[([^\]]+)\]\(([^\)]+)\)',
                    "fuzzy_threshold": 0.70,
                    "file_extensions": [".md", ".yaml"]
                },
                "detect_staleness": {
                    "enabled": True,
                    "staleness_threshold_days": 30
                },
                "sync_canonical": {
                    "enabled": True,
                    "source_file": str(source)
                }
            },
            "git": {
                "auto_commit": False,
                "commit_prefix": "[docs]"
            },
            "reporting": {
                "format": "markdown",
                "output_dir": "reports/"
            }
        }

        result = validate_config_schema(config, project_root=tmp_path)
        if not result.is_valid:
            print(f"Errors: {result.errors}")
        assert result.is_valid, f"Valid config failed: {result.errors}"
        assert len(result.warnings) == 0 or all("implemented" in w for w in result.warnings)

    def test_multiple_errors_collected(self, tmp_path):
        """Multiple config errors should all be reported."""
        config = {
            "project": {
                "root": str(tmp_path),
                "doc_root": str(tmp_path)
            },
            "confidence": {
                "auto_commit_threshold": 1.5,  # Error 1
                "auto_stage_threshold": -0.1,  # Error 2
            },
            "healers": {
                "fix_broken_links": {
                    "link_pattern": "[unclosed",  # Error 3
                    "fuzzy_threshold": "not_a_number"  # Error 4
                }
            }
        }

        result = validate_config_schema(config, project_root=tmp_path)
        assert not result.is_valid
        # Should have multiple errors
        assert len(result.errors) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
