#!/bin/bash
# Test install.py and rollback.py functionality

set -e

echo "🧪 Testing Doc Guardian Utilities"
echo "=================================="
echo ""

# Test 1: List hooks
echo "✅ Test 1: List available hooks"
python3 guardian/install.py --list
echo ""

# Test 2: Help messages
echo "✅ Test 2: Verify help messages"
python3 guardian/install.py --help > /dev/null
python3 guardian/rollback.py --help > /dev/null
echo "   Both help messages work"
echo ""

# Test 3: Show recent commits
echo "✅ Test 3: Show recent healing commits"
python3 guardian/rollback.py --show | head -5
echo ""

# Test 4: Syntax validation
echo "✅ Test 4: Python syntax validation"
python3 -m py_compile guardian/install.py
python3 -m py_compile guardian/rollback.py
echo "   Both scripts have valid syntax"
echo ""

echo "=================================="
echo "✅ All tests passed!"
echo ""
echo "To install hooks:"
echo "  python guardian/install.py"
echo ""
echo "To rollback changes:"
echo "  python guardian/rollback.py"
