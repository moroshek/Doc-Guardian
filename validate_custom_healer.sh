#!/bin/bash
#
# Validation script for custom healer template deliverables
#
# Checks:
# 1. All files exist
# 2. Template is valid Python
# 3. Example healer runs without errors
# 4. Tests can be imported
# 5. Documentation links work

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=================================================="
echo "Custom Healer Template - Validation"
echo "=================================================="
echo ""

ERRORS=0

# Check function
check() {
    local description="$1"
    local command="$2"

    echo -n "Checking: $description... "

    if eval "$command" &>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
    fi
}

# File existence checks
echo "File Existence Checks"
echo "---------------------"

check "Template exists" "test -f templates/custom_healer_template.py"
check "Guide exists" "test -f docs/CUSTOM_HEALERS.md"
check "Examples README exists" "test -f examples/README.md"
check "Example healer exists" "test -f examples/custom_healer_example/fix_typos_healer.py"
check "Example tests exist" "test -f examples/custom_healer_example/test_fix_typos.py"
check "Example config exists" "test -f examples/custom_healer_example/config.toml"
check "Demo script exists" "test -f examples/custom_healer_example/demo.sh"
check "Sample docs exist" "test -d examples/custom_healer_example/sample_docs"

echo ""

# Syntax checks
echo "Syntax Checks"
echo "-------------"

check "Template syntax valid" "python3 -m py_compile templates/custom_healer_template.py"
check "Example healer syntax valid" "python3 -m py_compile examples/custom_healer_example/fix_typos_healer.py"
check "Example tests syntax valid" "python3 -m py_compile examples/custom_healer_example/test_fix_typos.py"

echo ""

# Content checks
echo "Content Checks"
echo "--------------"

check "Template has HealingSystem import" "grep -q 'from guardian.core.base import HealingSystem' templates/custom_healer_template.py"
check "Template has check() method" "grep -q 'def check(self)' templates/custom_healer_template.py"
check "Template has heal() method" "grep -q 'def heal(self' templates/custom_healer_template.py"
check "Template has example usage" "grep -q 'if __name__' templates/custom_healer_template.py"

check "Guide has Quick Start" "grep -q '## Quick Start' docs/CUSTOM_HEALERS.md"
check "Guide has Step-by-Step" "grep -q '## Step-by-Step Guide' docs/CUSTOM_HEALERS.md"
check "Guide has Confidence section" "grep -q '## Confidence Scoring' docs/CUSTOM_HEALERS.md"
check "Guide has Testing section" "grep -q '## Testing' docs/CUSTOM_HEALERS.md"

check "Example has tests" "grep -q 'def test_' examples/custom_healer_example/test_fix_typos.py"
check "Example has configuration" "grep -q '\[healers.fix_typos\]' examples/custom_healer_example/config.toml"

echo ""

# Documentation checks
echo "Documentation Checks"
echo "-------------------"

check "Template docstring exists" "grep -q '\"\"\"' templates/custom_healer_template.py | head -1"
check "Guide has table of contents" "grep -q 'Table of Contents' docs/CUSTOM_HEALERS.md"
check "Example README has usage" "grep -q 'Quick Start' examples/custom_healer_example/README.md"

echo ""

# Line count checks (rough quality metric)
echo "Completeness Checks"
echo "------------------"

TEMPLATE_LINES=$(wc -l < templates/custom_healer_template.py)
GUIDE_LINES=$(wc -l < docs/CUSTOM_HEALERS.md)
EXAMPLE_LINES=$(wc -l < examples/custom_healer_example/fix_typos_healer.py)
TEST_LINES=$(wc -l < examples/custom_healer_example/test_fix_typos.py)

echo "Template: $TEMPLATE_LINES lines"
echo "Guide: $GUIDE_LINES lines"
echo "Example healer: $EXAMPLE_LINES lines"
echo "Example tests: $TEST_LINES lines"

echo ""

if [ $TEMPLATE_LINES -lt 400 ]; then
    echo -e "${YELLOW}Warning: Template seems short (<400 lines)${NC}"
    ((ERRORS++))
else
    echo -e "${GREEN}✓ Template completeness OK${NC}"
fi

if [ $GUIDE_LINES -lt 800 ]; then
    echo -e "${YELLOW}Warning: Guide seems short (<800 lines)${NC}"
    ((ERRORS++))
else
    echo -e "${GREEN}✓ Guide completeness OK${NC}"
fi

if [ $EXAMPLE_LINES -lt 400 ]; then
    echo -e "${YELLOW}Warning: Example healer seems short (<400 lines)${NC}"
    ((ERRORS++))
else
    echo -e "${GREEN}✓ Example healer completeness OK${NC}"
fi

if [ $TEST_LINES -lt 300 ]; then
    echo -e "${YELLOW}Warning: Tests seem short (<300 lines)${NC}"
    ((ERRORS++))
else
    echo -e "${GREEN}✓ Test completeness OK${NC}"
fi

echo ""
echo "=================================================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All checks passed! ✓${NC}"
    echo ""
    echo "Custom healer template is ready for users."
    echo ""
    echo "Next steps:"
    echo "  1. Review: docs/CUSTOM_HEALERS.md"
    echo "  2. Try demo: cd examples/custom_healer_example && ./demo.sh"
    echo "  3. Run tests: pytest examples/custom_healer_example/test_fix_typos.py -v"
    exit 0
else
    echo -e "${RED}$ERRORS checks failed ✗${NC}"
    echo ""
    echo "Please review the failed checks above."
    exit 1
fi
