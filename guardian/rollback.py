#!/usr/bin/env python3
"""
Doc Guardian Rollback Utility

Rollback healing changes using git or backup files.

Usage:
    python guardian/rollback.py                     # Interactive mode
    python guardian/rollback.py --commit abc123     # Revert specific commit
    python guardian/rollback.py --last              # Revert last healing commit
    python guardian/rollback.py --last 3            # Revert last 3 healing commits
    python guardian/rollback.py --backup FILE       # Restore from backup
"""

import sys
from pathlib import Path
from typing import List, Tuple, Optional
import argparse
import subprocess
import json
from datetime import datetime


def find_git_root() -> Path:
    """Find the git repository root"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print("❌ Not in a git repository")
        sys.exit(1)


def find_healing_commits(n: int = 10, pattern: str = "docs") -> List[Tuple[str, str, str]]:
    """
    Find recent healing commits

    Returns: List of (hash, date, message) tuples
    """
    try:
        # Search for commits with healing markers
        result = subprocess.run(
            ["git", "log", f"--grep=[{pattern}]", "--format=%H|%ai|%s", f"-{n}"],
            capture_output=True,
            text=True,
            check=True
        )

        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            parts = line.split('|', 2)
            if len(parts) == 3:
                hash_val, date, message = parts
                commits.append((hash_val, date, message))

        return commits

    except subprocess.CalledProcessError:
        return []


def show_commit_details(commit_hash: str) -> bool:
    """Show details of a commit"""
    try:
        print(f"\n📋 Commit details:")
        print("-" * 60)

        result = subprocess.run(
            ["git", "show", "--stat", "--format=%H%n%ai%n%an%n%s%n%b", commit_hash],
            capture_output=True,
            text=True,
            check=True
        )

        print(result.stdout)
        return True

    except subprocess.CalledProcessError:
        print(f"❌ Could not show commit {commit_hash}")
        return False


def get_changed_files(commit_hash: str) -> List[str]:
    """Get list of files changed in a commit"""
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
            capture_output=True,
            text=True,
            check=True
        )
        return [f for f in result.stdout.strip().split('\n') if f]

    except subprocess.CalledProcessError:
        return []


def rollback_commit(commit_hash: str, no_edit: bool = False) -> bool:
    """Rollback a specific commit using git revert"""
    print(f"\n🔄 Rolling back commit {commit_hash[:8]}...")

    try:
        # Show what will be reverted
        files = get_changed_files(commit_hash)
        if files:
            print(f"\n📄 Files that will be reverted:")
            for f in files[:10]:  # Show first 10
                print(f"   - {f}")
            if len(files) > 10:
                print(f"   ... and {len(files) - 10} more")

        # Confirm
        if not no_edit:
            response = input(f"\n❓ Revert this commit? [y/N]: ")
            if response.lower() != 'y':
                print("❌ Rollback cancelled")
                return False

        # Perform revert
        args = ["git", "revert", commit_hash]
        if no_edit:
            args.append("--no-edit")

        result = subprocess.run(args, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Rollback successful")
            return True
        else:
            print("❌ Rollback failed")
            if result.stderr:
                print(f"\nError: {result.stderr}")
            return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Rollback failed: {e}")
        return False


def find_backup_file(file_path: Path) -> Optional[Path]:
    """Find backup file for a given path"""
    # Common backup locations
    candidates = [
        file_path.with_suffix(file_path.suffix + '.backup'),
        file_path.with_suffix(file_path.suffix + '.bak'),
        file_path.parent / f".backup_{file_path.name}",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def rollback_from_backup(backup_file: Path, target_file: Optional[Path] = None) -> bool:
    """Restore file from backup"""
    if not backup_file.exists():
        print(f"❌ Backup file not found: {backup_file}")
        return False

    # Determine target file
    if target_file is None:
        # Try to infer from backup name
        if backup_file.suffix in ['.backup', '.bak']:
            target_file = backup_file.with_suffix('')
        else:
            print(f"❌ Cannot infer target file from backup name")
            print(f"   Use: --target FILE")
            return False

    print(f"\n📋 Restoring from backup:")
    print(f"   From: {backup_file}")
    print(f"   To:   {target_file}")

    # Confirm
    response = input(f"\n❓ Restore this file? [y/N]: ")
    if response.lower() != 'y':
        print("❌ Restore cancelled")
        return False

    try:
        # Create backup of current file
        if target_file.exists():
            current_backup = target_file.with_suffix(target_file.suffix + '.pre-restore')
            print(f"📋 Backing up current file to {current_backup.name}")
            target_file.rename(current_backup)

        # Restore from backup
        import shutil
        shutil.copy2(backup_file, target_file)

        print(f"✅ File restored successfully")
        return True

    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False


def interactive_mode():
    """Interactive rollback selection"""
    print("\n🔍 Searching for recent healing commits...")

    commits = find_healing_commits(n=20)

    if not commits:
        print("❌ No healing commits found in recent history")
        print("   Commits are identified by [docs] prefix")
        return False

    print(f"\n📝 Found {len(commits)} healing commits:")
    print("-" * 80)

    for i, (hash_val, date, message) in enumerate(commits, 1):
        # Truncate message if too long
        msg_short = message[:60] + "..." if len(message) > 60 else message
        print(f"{i:2}. {hash_val[:8]} {date[:10]} {msg_short}")

    print("-" * 80)

    # Get selection
    try:
        choice = input(f"\n❓ Select commit to rollback (1-{len(commits)}, or 'q' to quit): ")

        if choice.lower() == 'q':
            print("❌ Rollback cancelled")
            return False

        idx = int(choice) - 1
        if idx < 0 or idx >= len(commits):
            print(f"❌ Invalid selection")
            return False

        hash_val, date, message = commits[idx]

        print(f"\n📋 Selected commit:")
        print(f"   Hash:    {hash_val}")
        print(f"   Date:    {date}")
        print(f"   Message: {message}")

        # Show details and confirm
        show_commit_details(hash_val)

        return rollback_commit(hash_val, no_edit=False)

    except (ValueError, KeyboardInterrupt):
        print("\n❌ Rollback cancelled")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Rollback Doc Guardian healing changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode (select from recent commits):
    python guardian/rollback.py

  Revert specific commit:
    python guardian/rollback.py --commit abc123

  Revert last healing commit:
    python guardian/rollback.py --last

  Revert last 3 healing commits:
    python guardian/rollback.py --last 3

  Restore from backup file:
    python guardian/rollback.py --backup README.md.backup --target README.md

  Show recent healing commits:
    python guardian/rollback.py --show
        """
    )

    parser.add_argument('--commit', help="Commit hash to revert")
    parser.add_argument('--last', nargs='?', const=1, type=int,
                        help="Revert last N healing commits (default: 1)")
    parser.add_argument('--backup', type=Path, help="Restore from backup file")
    parser.add_argument('--target', type=Path, help="Target file for backup restore")
    parser.add_argument('--show', action='store_true', help="Show recent healing commits")
    parser.add_argument('--no-edit', action='store_true',
                        help="Don't prompt for commit message when reverting")
    parser.add_argument('--pattern', default='docs',
                        help="Git grep pattern for healing commits (default: 'docs')")

    args = parser.parse_args()

    # Find git root
    git_root = find_git_root()

    # Show mode
    if args.show:
        commits = find_healing_commits(n=20, pattern=args.pattern)
        if not commits:
            print(f"❌ No commits found matching pattern: [{args.pattern}]")
            sys.exit(1)

        print(f"\n📝 Recent healing commits (pattern: [{args.pattern}]):")
        print("-" * 80)

        for hash_val, date, message in commits:
            print(f"{hash_val[:8]} {date[:10]} {message}")

        print("-" * 80)
        sys.exit(0)

    # Backup restore mode
    if args.backup:
        success = rollback_from_backup(args.backup, args.target)
        sys.exit(0 if success else 1)

    # Revert last N commits mode
    if args.last:
        commits = find_healing_commits(n=args.last, pattern=args.pattern)

        if not commits:
            print(f"❌ No healing commits found")
            sys.exit(1)

        if len(commits) < args.last:
            print(f"⚠️  Found only {len(commits)} commits (requested {args.last})")

        print(f"\n🔄 Reverting last {len(commits)} healing commit(s):")

        success_count = 0
        for hash_val, date, message in commits:
            print(f"\n{'='*60}")
            print(f"Commit: {hash_val[:8]} - {message}")

            if rollback_commit(hash_val, no_edit=args.no_edit):
                success_count += 1
            else:
                print(f"\n⚠️  Failed to revert, stopping here")
                break

        print(f"\n✅ Reverted {success_count}/{len(commits)} commits")
        sys.exit(0 if success_count == len(commits) else 1)

    # Revert specific commit mode
    if args.commit:
        success = rollback_commit(args.commit, no_edit=args.no_edit)
        sys.exit(0 if success else 1)

    # Interactive mode (default)
    success = interactive_mode()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
