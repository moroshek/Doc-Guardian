#!/bin/bash
# Verification script to confirm all intentional issues are present

echo "=== Markdown Wiki Issue Verification ==="
echo ""

# Count broken links
echo "1. Checking for broken links..."
BROKEN_COUNT=$(grep -rn "](connectors.md)\|](patterns-guide.md)\|](.*deployment-guide.md)\|](.*user-manual.md)\|](config.md)\|](migration-v2.md)\|](.*security-config.md)\|](.*architecture/" docs/ | wc -l)
echo "   Found $BROKEN_COUNT references to potentially non-existent files"
echo ""
echo "   Specific broken links:"
grep -rn "](connectors.md)\|](patterns-guide.md)\|](.*deployment-guide.md)\|](.*user-manual.md)\|](config.md)\|](migration-v2.md)\|](.*security-config.md)\|](.*architecture/" docs/ | head -15

# Check stale timestamps
echo ""
echo "2. Checking for stale timestamps (2024 dates)..."
STALE_COUNT=$(grep -r "\*\*Last Updated:\*\* 2024-" docs/ | wc -l)
echo "   Found $STALE_COUNT files with 2024 dates (expected: 3)"
grep -r "\*\*Last Updated:\*\* 2024-" docs/ | sed 's/^/   /'

# Count long sections
echo ""
echo "3. Checking for long sections..."
echo "   File sizes (candidates for section collapse):"

for file in docs/guides/user-guide.md docs/guides/admin-guide.md docs/guides/troubleshooting.md; do
    if [ -f "$file" ]; then
        LINES=$(wc -l < "$file")
        echo "   - $file: $LINES lines"
    fi
done

# Summary
echo ""
echo "=== Summary ==="
echo "Total markdown files: $(find docs -name "*.md" | wc -l)"
echo "Total lines of documentation: $(find docs -name "*.md" -exec wc -l {} \; | awk '{sum+=$1} END {print sum}')"
echo ""
echo "✓ Issues verified and ready for Doc Guardian testing"
echo ""
echo "Run Doc Guardian with:"
echo "  cargo run --bin doc-guardian -- audit"
