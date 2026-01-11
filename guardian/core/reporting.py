"""
Report generation for healing operations.

Provides utilities to generate reports in:
- Markdown format (human-readable)
- JSON format (machine-readable)
- Console output (terminal-friendly)
"""

import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from .base import HealingReport, Change


def generate_markdown_report(report: HealingReport) -> str:
    """
    Generate markdown format report.

    Format:
    # Healing Report: {healer_name}

    **Mode**: check/heal
    **Timestamp**: ISO timestamp
    **Execution Time**: X.XX seconds

    ## Summary
    - Issues found: X
    - Issues fixed: X
    - Success rate: XX%

    ## Changes

    ### {file}:{line}
    - **Confidence**: XX%
    - **Reason**: {reason}
    - **Old**: {old_content}
    - **New**: {new_content}

    ## Errors
    - {error1}
    - {error2}

    Args:
        report: HealingReport instance

    Returns:
        Markdown formatted report as string
    """
    lines = []

    # Header
    lines.append(f"# Healing Report: {report.healer_name}\n")
    lines.append(f"**Mode**: {report.mode}\n")
    lines.append(f"**Timestamp**: {report.timestamp}\n")
    lines.append(f"**Execution Time**: {report.execution_time:.2f} seconds\n")

    # Summary
    lines.append("\n## Summary\n")
    lines.append(f"- **Issues found**: {report.issues_found}\n")
    lines.append(f"- **Issues fixed**: {report.issues_fixed}\n")
    lines.append(f"- **Success rate**: {report.success_rate*100:.1f}%\n")

    # Status indicator
    if report.issues_found == 0:
        lines.append("\n✅ **All documentation is healthy!**\n")
    elif report.issues_fixed == report.issues_found:
        lines.append("\n✅ **All issues fixed!**\n")
    elif report.issues_fixed > 0:
        lines.append(f"\n⚠️ **{report.issues_found - report.issues_fixed} issues remaining**\n")
    else:
        lines.append("\n⚠️ **No issues fixed (check mode or low confidence)**\n")

    # Changes
    if report.changes:
        lines.append("\n## Changes\n")

        # Group by file
        changes_by_file: Dict[Path, list] = {}
        for change in report.changes:
            if change.file not in changes_by_file:
                changes_by_file[change.file] = []
            changes_by_file[change.file].append(change)

        for file_path, file_changes in sorted(changes_by_file.items()):
            lines.append(f"\n### {file_path}\n")

            for change in file_changes:
                lines.append(f"\n#### Line {change.line}\n")
                lines.append(f"- **Confidence**: {change.confidence*100:.0f}%\n")
                lines.append(f"- **Reason**: {change.reason}\n")
                lines.append(f"- **Healer**: {change.healer}\n")

                # Show diff
                if change.old_content:
                    lines.append("\n**Old**:\n```\n")
                    lines.append(change.old_content[:200])  # Limit to 200 chars
                    if len(change.old_content) > 200:
                        lines.append("...")
                    lines.append("\n```\n")

                lines.append("\n**New**:\n```\n")
                lines.append(change.new_content[:200])
                if len(change.new_content) > 200:
                    lines.append("...")
                lines.append("\n```\n")

    # Errors
    if report.errors:
        lines.append("\n## Errors\n")
        for error in report.errors:
            lines.append(f"- {error}\n")

    return ''.join(lines)


def generate_json_report(report: HealingReport) -> Dict[str, Any]:
    """
    Generate JSON format report.

    Structure:
    {
        "healer_name": str,
        "mode": str,
        "timestamp": str,
        "execution_time": float,
        "summary": {
            "issues_found": int,
            "issues_fixed": int,
            "success_rate": float
        },
        "changes": [
            {
                "file": str,
                "line": int,
                "confidence": float,
                "reason": str,
                "old_content": str,
                "new_content": str,
                "healer": str
            }
        ],
        "errors": [str]
    }

    Args:
        report: HealingReport instance

    Returns:
        Dict suitable for JSON serialization
    """
    return {
        "healer_name": report.healer_name,
        "mode": report.mode,
        "timestamp": report.timestamp,
        "execution_time": report.execution_time,
        "summary": {
            "issues_found": report.issues_found,
            "issues_fixed": report.issues_fixed,
            "success_rate": report.success_rate
        },
        "changes": [
            {
                "file": str(change.file),
                "line": change.line,
                "confidence": change.confidence,
                "reason": change.reason,
                "old_content": change.old_content,
                "new_content": change.new_content,
                "healer": change.healer
            }
            for change in report.changes
        ],
        "errors": report.errors
    }


def generate_console_output(report: HealingReport, verbose: bool = False) -> str:
    """
    Generate console-friendly output with colors and symbols.

    Args:
        report: HealingReport instance
        verbose: If True, show detailed change information

    Returns:
        Formatted string for terminal output
    """
    lines = []

    # Header with box
    lines.append("=" * 70)
    lines.append(f"Healing Report: {report.healer_name}")
    lines.append("=" * 70)

    # Summary
    lines.append(f"\nMode: {report.mode}")
    lines.append(f"Execution time: {report.execution_time:.2f}s")
    lines.append(f"\n📊 Summary:")
    lines.append(f"   Issues found: {report.issues_found}")
    lines.append(f"   Issues fixed: {report.issues_fixed}")
    lines.append(f"   Success rate: {report.success_rate*100:.1f}%")

    # Status
    if report.issues_found == 0:
        lines.append("\n✅ All documentation is healthy!")
    elif report.issues_fixed == report.issues_found:
        lines.append("\n✅ All issues fixed!")
    elif report.issues_fixed > 0:
        remaining = report.issues_found - report.issues_fixed
        lines.append(f"\n⚠️  {remaining} issues remaining")

    # Changes (if verbose)
    if verbose and report.changes:
        lines.append(f"\n🔧 Changes ({len(report.changes)}):")

        for i, change in enumerate(report.changes[:10], 1):  # Limit to 10
            conf_emoji = "🟢" if change.confidence >= 0.9 else "🟡" if change.confidence >= 0.7 else "🔴"
            lines.append(f"\n{i}. {conf_emoji} {change.file}:{change.line}")
            lines.append(f"   Confidence: {change.confidence*100:.0f}%")
            lines.append(f"   Reason: {change.reason}")

        if len(report.changes) > 10:
            lines.append(f"\n   ... and {len(report.changes) - 10} more")

    # Errors
    if report.errors:
        lines.append(f"\n❌ Errors ({len(report.errors)}):")
        for error in report.errors[:5]:  # Limit to 5
            lines.append(f"   - {error}")
        if len(report.errors) > 5:
            lines.append(f"   ... and {len(report.errors) - 5} more")

    lines.append("\n" + "=" * 70)

    return '\n'.join(lines)


def save_report(report: HealingReport, output_dir: Path, format: str = 'markdown'):
    """
    Save report to disk.

    Filename format: {healer_name}_{timestamp}.{ext}

    Args:
        report: HealingReport instance
        output_dir: Directory to save report
        format: "markdown", "json", or "both"

    Example:
        >>> report = HealingReport(...)
        >>> save_report(report, Path("reports/"), format="both")
        # Creates:
        # reports/BrokenLinkHealer_20240315_143022.md
        # reports/BrokenLinkHealer_20240315_143022.json
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for filename
    timestamp = datetime.fromisoformat(report.timestamp).strftime("%Y%m%d_%H%M%S")
    base_name = f"{report.healer_name}_{timestamp}"

    if format in ['markdown', 'both']:
        md_path = output_dir / f"{base_name}.md"
        md_content = generate_markdown_report(report)
        md_path.write_text(md_content)

    if format in ['json', 'both']:
        json_path = output_dir / f"{base_name}.json"
        json_data = generate_json_report(report)
        json_path.write_text(json.dumps(json_data, indent=2))
