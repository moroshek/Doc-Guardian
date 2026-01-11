"""
Example usage of ManageCollapsedHealer.

This demonstrates how to use the healer in a project.
"""

from pathlib import Path
from guardian.healers.manage_collapsed import ManageCollapsedHealer

# Example configuration
config = {
    'project': {
        'root': '/path/to/your/project',
        'doc_root': '/path/to/your/project/docs'
    },
    'confidence': {
        'auto_commit_threshold': 0.8,
        'auto_stage_threshold': 0.7
    },
    'reporting': {
        'output_dir': '/path/to/your/project/.guardian/reports'
    },
    'healers': {
        'manage_collapsed': {
            # Hint generation strategy:
            # - 'summary': Count code blocks/commands/bullets (default)
            # - 'first_sentence': Use first sentence of content
            # - 'keywords': Use most common keywords
            'hint_strategy': 'summary',

            # Track usage analytics (requires external tracking)
            'track_usage': False,

            # Line count threshold for flagging long sections
            'long_section_threshold': 500,

            # Ratio of missing keywords that triggers issue
            'missing_keywords_threshold': 0.5,

            # Custom stopwords for keyword extraction (optional)
            'stopwords': ['the', 'and', 'for', 'are', 'but']
        }
    }
}

# Initialize healer
healer = ManageCollapsedHealer(config)

# Check mode - analyze without making changes
print("Running check...")
check_report = healer.check()

print(f"Found {check_report.issues_found} issues")
print(f"Execution time: {check_report.execution_time:.2f}s")

# Print proposed changes
for change in check_report.changes:
    print(f"\nFile: {change.file}")
    print(f"Line: {change.line}")
    print(f"Reason: {change.reason}")
    print(f"Confidence: {change.confidence:.0%}")
    if change.old_content and change.new_content:
        print(f"Old: {change.old_content[:50]}...")
        print(f"New: {change.new_content[:50]}...")

# Heal mode - apply fixes above confidence threshold
print("\n" + "="*60)
print("Running heal...")
heal_report = healer.heal(min_confidence=0.8)

print(f"Fixed {heal_report.issues_fixed}/{heal_report.issues_found} issues")
print(f"Success rate: {heal_report.success_rate:.0%}")

if heal_report.has_errors:
    print("\nErrors encountered:")
    for error in heal_report.errors:
        print(f"  - {error}")

# Example output:
# Running check...
# Found 3 issues
# Execution time: 0.12s
#
# File: /path/to/docs/guide.md
# Line: 45
# Reason: Section 'Installation' lacks expand hint
# Confidence: 85%
# Old: <summary>Installation</summary>
# New: <summary>Installation (Expand to see: 5 commands)</summary>
#
# ============================================================
# Running heal...
# Fixed 2/3 issues
# Success rate: 67%
