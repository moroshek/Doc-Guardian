"""
Test Python version and platform compatibility.

These tests verify that doc-guardian works correctly across:
- Python versions 3.8-3.12
- Linux, macOS, Windows platforms
- Different path separators and line endings
"""

import sys
import os
import platform
from pathlib import Path


def test_python_version():
    """Verify Python version is 3.8 or newer."""
    assert sys.version_info >= (3, 8), (
        f"Python 3.8+ required, but running {sys.version_info.major}.{sys.version_info.minor}"
    )


def test_required_stdlib_modules():
    """Verify all required stdlib modules can be imported."""
    required_modules = [
        'pathlib',
        're',
        'json',
        'subprocess',
        'dataclasses',
        'typing',
        'argparse',
        'logging',
        'hashlib',
        'difflib',
        'collections',
        'concurrent.futures',
        'tempfile',
        'signal',
        'contextlib',
        'functools',
        'abc',
        'datetime',
    ]

    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError as e:
            raise AssertionError(f"Required stdlib module '{module_name}' not available: {e}")


def test_core_imports():
    """Test that core guardian modules can be imported."""
    # Add parent directory to path if running from source
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from guardian.core.base import Change
        from guardian.core.logger import HealerLogger
        from guardian.core.git_utils import is_git_repo
        from guardian.core.security import safe_read_file
        from guardian.heal import main
        from guardian.install import main as install_main
    except ImportError as e:
        raise AssertionError(f"Failed to import core guardian modules: {e}")


def test_all_modules_importable():
    """Test that all guardian modules can be imported without errors.

    This catches Python 3.8 compatibility issues like using tuple[x, y]
    instead of Tuple[x, y] which would fail at import time.
    """
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    modules_to_test = [
        'guardian',
        'guardian.core',
        'guardian.core.base',
        'guardian.core.logger',
        'guardian.core.git_utils',
        'guardian.core.security',
        'guardian.core.atomic_write',
        'guardian.core.path_validator',
        'guardian.core.regex_validator',
        'guardian.core.config_validator',
        'guardian.core.confidence',
        'guardian.core.validation',
        'guardian.core.file_cache',
        'guardian.core.signal_handlers',
        'guardian.core.reporting',
        'guardian.core.colors',
        'guardian.healers',
        'guardian.healers.fix_broken_links',
        'guardian.healers.sync_canonical',
        'guardian.healers.detect_staleness',
        'guardian.healers.balance_references',
        'guardian.healers.manage_collapsed',
        'guardian.healers.resolve_duplicates',
        'guardian.healers.enforce_disclosure',
        'guardian.heal',
        'guardian.install',
        'guardian.rollback',
    ]

    import_errors = []
    for module_name in modules_to_test:
        try:
            __import__(module_name)
        except Exception as e:
            import_errors.append((module_name, str(e)))

    if import_errors:
        msg = "Failed to import modules:\n"
        for module, error in import_errors:
            msg += f"  {module}: {error}\n"
        raise AssertionError(msg)


def test_walrus_operator_support():
    """Test that walrus operator (:=) works (Python 3.8+ feature)."""
    # This is the syntax used in sync_canonical.py
    result = None
    if (result := "test") == "test":
        assert result == "test"
    else:
        raise AssertionError("Walrus operator not working")


def test_dataclasses_support():
    """Test that dataclasses work correctly."""
    from dataclasses import dataclass

    @dataclass
    class TestClass:
        name: str
        value: int = 0

    obj = TestClass(name="test", value=42)
    assert obj.name == "test"
    assert obj.value == 42


def test_typing_support():
    """Test that typing module features work."""
    from typing import List, Dict, Optional, Tuple

    # Test basic type annotations work
    def test_func(items: List[str], mapping: Dict[str, int]) -> Optional[Tuple[str, int]]:
        if items and mapping:
            return (items[0], mapping.get(items[0], 0))
        return None

    result = test_func(["a"], {"a": 1})
    assert result == ("a", 1)


def test_no_python39_builtin_generics():
    """
    Verify code uses typing.List/Dict/Tuple, not list[]/dict[]/tuple[] (Python 3.9+).

    On Python 3.8, builtin types like list, dict, tuple are not subscriptable.
    Using list[str] instead of List[str] causes TypeError at import time on 3.8.
    """
    import ast
    import re
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    guardian_dir = project_root / 'guardian'

    # Pattern to detect Python 3.9+ builtin generics in annotations
    # Matches: -> list[, -> dict[, -> tuple[, -> set[
    # Also matches: param: list[, param: dict[, etc.
    builtin_generic_pattern = re.compile(
        r':\s*(?:list|dict|tuple|set|frozenset)\s*\[|'
        r'->\s*(?:list|dict|tuple|set|frozenset)\s*\['
    )

    violations = []

    for py_file in guardian_dir.rglob('*.py'):
        try:
            content = py_file.read_text()

            # Skip comments and docstrings by parsing AST
            # But for simplicity, just search raw content and filter out docstrings
            for i, line in enumerate(content.split('\n'), 1):
                # Skip if line is a comment
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue

                # Check for builtin generics
                if builtin_generic_pattern.search(line):
                    # Make sure it's not in a string/docstring
                    # Simple heuristic: if line contains '"""' or "'''" it might be docstring
                    if '"""' in line or "'''" in line:
                        continue
                    violations.append((py_file.relative_to(project_root), i, line.strip()))
        except Exception as e:
            pass  # Skip files that can't be read

    if violations:
        msg = "Python 3.9+ builtin generics found (use typing.List/Dict/Tuple instead):\n"
        for path, line_num, line in violations[:5]:
            msg += f"  {path}:{line_num}: {line[:80]}\n"
        if len(violations) > 5:
            msg += f"  ... and {len(violations) - 5} more\n"
        raise AssertionError(msg)


def test_path_handling():
    """Test that pathlib works correctly on current platform."""
    # Test basic path operations
    p = Path("/tmp/test/file.txt")
    assert p.name == "file.txt"
    assert p.suffix == ".txt"
    assert p.stem == "file"

    # Test path joining works
    p2 = Path("/tmp") / "test" / "file.txt"
    assert p2.as_posix() == "/tmp/test/file.txt"

    # Test relative paths
    p3 = Path("docs/guide.md")
    assert p3.parts == ("docs", "guide.md")


def test_platform_detection():
    """Test that we can detect the current platform."""
    system = platform.system()
    assert system in ["Linux", "Darwin", "Windows"], f"Unknown platform: {system}"

    # Test that we can get useful platform info
    assert platform.python_version()
    assert platform.machine()


def test_utf8_encoding():
    """Test that UTF-8 text handling works."""
    import tempfile

    # Test UTF-8 content
    test_content = "Hello 世界 🌍 Ñoño"

    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
        f.write(test_content)
        temp_path = f.name

    try:
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert content == test_content, "UTF-8 content not preserved"
    finally:
        os.unlink(temp_path)


def test_line_endings():
    """Test that different line endings are handled."""
    import tempfile

    # Test LF (Unix)
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        f.write(b"line1\nline2\n")
        temp_lf = f.name

    try:
        with open(temp_lf, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 2
    finally:
        os.unlink(temp_lf)

    # Test CRLF (Windows)
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        f.write(b"line1\r\nline2\r\n")
        temp_crlf = f.name

    try:
        with open(temp_crlf, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 2
    finally:
        os.unlink(temp_crlf)


def test_concurrent_futures():
    """Test that parallel processing works."""
    from concurrent.futures import ThreadPoolExecutor

    def square(x):
        return x * x

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(square, [1, 2, 3, 4]))

    assert results == [1, 4, 9, 16]


def test_regex_patterns():
    """Test that regex patterns work correctly."""
    import re

    # Test patterns used in doc-guardian
    link_pattern = r'\[([^\]]*)\]\(([^\)]*)\)'
    text = "[Doc Guardian](https://github.com/example)"

    match = re.search(link_pattern, text)
    assert match
    assert match.group(1) == "Doc Guardian"
    assert match.group(2) == "https://github.com/example"


def test_json_handling():
    """Test that JSON serialization works."""
    import json

    data = {
        "name": "test",
        "values": [1, 2, 3],
        "nested": {"key": "value"},
    }

    # Test round-trip
    serialized = json.dumps(data)
    deserialized = json.loads(serialized)
    assert deserialized == data


def test_tempfile_operations():
    """Test that temporary file operations work (used in atomic_write)."""
    import tempfile

    # Test NamedTemporaryFile
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("test content")
        temp_path = f.name

    try:
        assert os.path.exists(temp_path)
        with open(temp_path, 'r') as f:
            assert f.read() == "test content"
    finally:
        os.unlink(temp_path)


def test_signal_handling():
    """Test that signal module works (used for graceful shutdown)."""
    import signal

    # Just verify we can access signal constants
    assert hasattr(signal, 'SIGINT')
    assert hasattr(signal, 'SIGTERM')

    # Test we can get current handlers (should not raise)
    original = signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGINT, original)


if __name__ == "__main__":
    # Run tests manually if pytest not available
    import inspect

    test_functions = [
        obj for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    ]

    print(f"Running {len(test_functions)} compatibility tests...\n")

    failed = []
    for func in test_functions:
        try:
            func()
            print(f"✓ {func.__name__}")
        except Exception as e:
            print(f"✗ {func.__name__}: {e}")
            failed.append((func.__name__, e))

    print(f"\n{len(test_functions) - len(failed)}/{len(test_functions)} tests passed")

    if failed:
        print("\nFailed tests:")
        for name, error in failed:
            print(f"  - {name}: {error}")
        sys.exit(1)
    else:
        print("\n✓ All compatibility tests passed!")
        sys.exit(0)
