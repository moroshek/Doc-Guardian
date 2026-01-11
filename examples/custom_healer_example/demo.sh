#!/bin/bash
#
# Demo script for Fix Typos Healer
#
# This script demonstrates the complete workflow:
# 1. Check for typos (dry run)
# 2. Show what would be fixed
# 3. Apply fixes
# 4. Verify results

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "Fix Typos Healer - Demo"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi

echo -e "${BLUE}Step 1: Show sample documentation with typos${NC}"
echo "---------------------------------------------------"
echo "guide.md excerpt:"
head -n 15 sample_docs/guide.md
echo ""
echo "(Full files in sample_docs/)"
echo ""

read -p "Press Enter to continue..."
echo ""

echo -e "${BLUE}Step 2: Run check (dry run - no changes)${NC}"
echo "---------------------------------------------------"
python3 fix_typos_healer.py
echo ""

read -p "Press Enter to apply fixes..."
echo ""

echo -e "${BLUE}Step 3: Applying fixes...${NC}"
echo "---------------------------------------------------"

# Backup originals
cp sample_docs/guide.md sample_docs/guide.md.backup
cp sample_docs/reference.md sample_docs/reference.md.backup

# Run healer
python3 fix_typos_healer.py

echo ""
echo -e "${GREEN}✓ Fixes applied!${NC}"
echo ""

echo -e "${BLUE}Step 4: Show corrected documentation${NC}"
echo "---------------------------------------------------"
echo "guide.md excerpt (corrected):"
head -n 15 sample_docs/guide.md
echo ""

echo -e "${BLUE}Step 5: Compare changes${NC}"
echo "---------------------------------------------------"

if command -v diff &> /dev/null; then
    echo "Changes in guide.md:"
    diff -u sample_docs/guide.md.backup sample_docs/guide.md || true
    echo ""
else
    echo "Install 'diff' to see detailed changes"
fi

echo ""
echo -e "${GREEN}Demo complete!${NC}"
echo ""
echo "What was fixed:"
echo "  - 'teh' → 'the'"
echo "  - 'recieve' → 'receive'"
echo "  - 'occured' → 'occurred'"
echo "  - 'untill' → 'until'"
echo "  - 'thier' → 'their'"
echo "  - 'wierd' → 'weird'"
echo "  - 'paramater' → 'parameter'"
echo "  - 'enviroment' → 'environment'"
echo "  - 'succesfully' → 'successfully'"
echo ""
echo "Notes:"
echo "  - Code blocks were skipped (typos preserved intentionally)"
echo "  - Case was preserved (Teh → The)"
echo "  - High confidence scores (0.95+) enabled auto-commit"
echo ""

read -p "Restore original files? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mv sample_docs/guide.md.backup sample_docs/guide.md
    mv sample_docs/reference.md.backup sample_docs/reference.md
    echo "Originals restored"
else
    rm -f sample_docs/*.backup
    echo "Kept fixed versions"
fi

echo ""
echo "Next steps:"
echo "  1. Run tests: pytest test_fix_typos.py -v"
echo "  2. Customize: Edit config.toml to add your typos"
echo "  3. Install: cp fix_typos_healer.py ../../guardian/healers/"
echo ""
