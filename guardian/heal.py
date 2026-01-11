#!/usr/bin/env python3
"""
Universal Documentation Healing Orchestrator

Runs all enabled healing systems in dependency order and generates unified report.

This is a generalized version of TCF's heal_all.py, extracted for use in the
Doc Guardian universal healing system.

Features:
- Sequential execution respecting healer dependencies
- Parallel execution for independent healers (with --parallel flag)
- Graceful shutdown handling (Ctrl+C)
- Multi-format config support (YAML/TOML)

Usage:
    python heal.py --config path/to/config.yaml --list
    python heal.py --config path/to/config.yaml --check
    python heal.py --config path/to/config.yaml --heal
    python heal.py --config path/to/config.yaml --heal --parallel
    python heal.py --config path/to/config.yaml --heal --only fix_broken_links
    python heal.py --config path/to/config.yaml --heal --skip enforce_disclosure

Performance:
- With --parallel: Independent healers run in parallel using ProcessPoolExecutor
- Target: < 10s for 1,000 files (from original 45-290s)
"""

import sys
import signal
from pathlib import Path

# Handle script execution - add parent to path before any local imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from dataclasses import dataclass, field
from typing import List, Dict, Type, Optional, Tuple, Callable
from datetime import datetime

# Now import local modules (works for both script and module)
try:
    from .core.base import HealingSystem, HealingReport, Change
    from .core.config_validator import (
        validate_config_schema,
        validate_and_load_config,
        ValidationResult,
        ConfigError,
        ConfigValidationError
    )
    from .core.colors import (
        Colors,
        colorize,
        success,
        error,
        warning,
        info,
        bold,
        show_progress,
        print_box
    )
except ImportError:
    from guardian.core.base import HealingSystem, HealingReport, Change
    from guardian.core.config_validator import (
        validate_config_schema,
        validate_and_load_config,
        ValidationResult,
        ConfigError,
        ConfigValidationError
    )
    from guardian.core.colors import (
        Colors,
        colorize,
        success,
        error,
        warning,
        info,
        bold,
        show_progress,
        print_box
    )

# Global flag for graceful shutdown
_shutdown_requested = False

def _signal_handler(signum, frame):
    """Handle Ctrl+C and SIGTERM for graceful shutdown."""
    global _shutdown_requested
    # Import here to avoid circular dependency
    from guardian.core.colors import error, warning

    if _shutdown_requested:
        # Force exit on second signal
        print(error("\n\nForced exit requested."), file=sys.stderr)
        sys.exit(1)
    _shutdown_requested = True
    print(warning("\n\nShutdown requested. Finishing current operation..."), file=sys.stderr)
    print(warning("Press Ctrl+C again to force exit."), file=sys.stderr)

# Install signal handlers
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# Config loading support for Python 3.11+
try:
    import tomllib
    TOML_AVAILABLE = True
except ImportError:
    try:
        import toml as tomllib
        TOML_AVAILABLE = True
    except ImportError:
        TOML_AVAILABLE = False

# YAML support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class UnifiedReport:
    """Aggregated report from all healing systems"""
    timestamp: str
    mode: str
    total_issues_found: int
    total_issues_fixed: int
    healer_reports: List[HealingReport]
    execution_time: float
    config_path: str

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate"""
        if self.total_issues_found == 0:
            return 1.0
        return self.total_issues_fixed / self.total_issues_found

    @property
    def has_errors(self) -> bool:
        """Check if any healers had errors"""
        return any(report.has_errors for report in self.healer_reports)


class HealingOrchestrator:
    """
    Orchestrates all healing systems in dependency order.

    Configuration-driven orchestrator that:
    1. Loads config from YAML/TOML
    2. Discovers and instantiates enabled healers
    3. Runs healers in dependency order
    4. Aggregates results into unified report
    5. Handles failures gracefully

    Healer Dependency Order:
        sync_canonical → fix_broken_links → detect_staleness →
        resolve_duplicates → balance_references → manage_collapsed →
        enforce_disclosure
    """

    # Default dependency order - can be overridden in config
    DEFAULT_HEALER_ORDER = [
        'sync_canonical',      # Run first (updates source data)
        'fix_broken_links',    # Fix links before checking references
        'detect_staleness',    # Update timestamps
        'resolve_duplicates',  # Consolidate content
        'balance_references',  # Add bidirectional links
        'manage_collapsed',    # Manage collapsed sections
        'enforce_disclosure',  # Check structure (last)
    ]

    def __init__(
        self,
        config: Dict,
        config_path: Optional[Path] = None,
        skip_healers: Optional[List[str]] = None,
        only_healer: Optional[str] = None,
        min_confidence: Optional[float] = None,
        continue_on_error: bool = False,
        verbose: bool = False,
        quiet: bool = False
    ):
        """
        Initialize orchestrator.

        Args:
            config: Configuration dictionary
            config_path: Path to config file (for reporting)
            skip_healers: List of healer names to skip
            only_healer: Run only this healer
            min_confidence: Override confidence threshold
            continue_on_error: Continue running even if a healer fails
            verbose: Show detailed progress
            quiet: Minimal output (errors only)
        """
        self.config = config
        self.config_path = config_path
        self.skip_healers = skip_healers or []
        self.only_healer = only_healer
        self.min_confidence = min_confidence or config.get('confidence', {}).get('auto_commit_threshold', 0.9)
        self.continue_on_error = continue_on_error
        self.verbose = verbose
        self.quiet = quiet

        # Discover healers
        self.available_healers = self._discover_healers()

        # Get healer order from config or use default
        self.healer_order = config.get('healer_order', self.DEFAULT_HEALER_ORDER)

    def _discover_healers(self) -> Dict[str, Type[HealingSystem]]:
        """
        Discover available healers from guardian.healers package.

        Returns:
            Dict mapping healer name to healer class
        """
        try:
            from . import healers
        except ImportError:
            from guardian import healers

        healer_map = {
            'sync_canonical': healers.SyncCanonicalHealer,
            'fix_broken_links': healers.FixBrokenLinksHealer,
            'detect_staleness': healers.DetectStalenessHealer,
            'resolve_duplicates': healers.ResolveDuplicatesHealer,
            'balance_references': healers.BalanceReferencesHealer,
            'manage_collapsed': healers.ManageCollapsedHealer,
            'enforce_disclosure': healers.EnforceDisclosureHealer,
        }

        # Filter by enabled in config
        enabled_healers = {}
        healers_config = self.config.get('healers', {})

        for name, healer_class in healer_map.items():
            healer_config = healers_config.get(name, {})
            if healer_config.get('enabled', True):  # Default to enabled
                enabled_healers[name] = healer_class

        return enabled_healers

    def _instantiate_healer(self, healer_name: str) -> Optional[HealingSystem]:
        """
        Create healer instance with configuration.

        Args:
            healer_name: Name of healer to instantiate

        Returns:
            HealingSystem instance or None if not available
        """
        healer_class = self.available_healers.get(healer_name)
        if not healer_class:
            return None

        try:
            return healer_class(self.config)
        except Exception as e:
            if self.verbose:
                print(f"   ❌ Failed to instantiate {healer_name}: {e}")
            return None

    def run_healer(self, healer_name: str, mode: str) -> HealingReport:
        """
        Run a single healing system.

        Args:
            healer_name: Name of healer to run
            mode: 'check' or 'heal'

        Returns:
            HealingReport from the healer
        """
        start_time = time.time()

        # Check if skipped
        if healer_name in self.skip_healers:
            return HealingReport(
                healer_name=healer_name,
                mode=mode,
                timestamp=datetime.now().isoformat(),
                issues_found=0,
                issues_fixed=0,
                errors=["Skipped by --skip flag"],
                execution_time=0.0
            )

        # Instantiate healer
        healer = self._instantiate_healer(healer_name)
        if not healer:
            return HealingReport(
                healer_name=healer_name,
                mode=mode,
                timestamp=datetime.now().isoformat(),
                issues_found=0,
                issues_fixed=0,
                errors=[f"Healer not available: {healer_name}"],
                execution_time=0.0
            )

        try:
            # Run check or heal
            if mode == 'check':
                report = healer.check()
            else:  # heal
                report = healer.heal(min_confidence=self.min_confidence)

            # Update execution time
            report.execution_time = time.time() - start_time
            return report

        except Exception as e:
            return HealingReport(
                healer_name=healer_name,
                mode=mode,
                timestamp=datetime.now().isoformat(),
                issues_found=0,
                issues_fixed=0,
                errors=[f"Exception: {str(e)}"],
                execution_time=time.time() - start_time
            )

    def run_all(self, mode: str = 'check') -> UnifiedReport:
        """
        Run all enabled healing systems in dependency order.

        Args:
            mode: 'check' or 'heal'

        Returns:
            UnifiedReport with aggregated results
        """
        start_time = time.time()
        reports = []

        if not self.quiet:
            mode_text = bold(f"{mode.upper()}")
            print(f"🔧 Running documentation healing systems ({mode_text} mode)...\n")

        # Determine which healers to run
        if self.only_healer:
            healers_to_run = [self.only_healer]
        else:
            # Filter order by available healers
            healers_to_run = [
                name for name in self.healer_order
                if name in self.available_healers
            ]

        total_healers = len(healers_to_run)

        # Run healers in order
        for idx, healer_name in enumerate(healers_to_run, 1):
            # Check for shutdown request (Ctrl+C handling)
            global _shutdown_requested
            if _shutdown_requested:
                if not self.quiet:
                    print(warning(f"\n⚠️  Shutdown requested, stopping after current operation"))
                break

            if not self.quiet:
                healer_display = bold(healer_name.replace('_', ' ').title())
                print(f"▶️  [{idx}/{total_healers}] Running {healer_display}...")

            report = self.run_healer(healer_name, mode)
            reports.append(report)

            if self.verbose:
                if report.has_errors:
                    print(error(f"   ❌ Failed: {report.errors[0] if report.errors else 'Unknown error'}"))
                    if len(report.errors) > 1:
                        print(error(f"      Run with --verbose to see all {len(report.errors)} errors"))
                elif report.issues_found > 0:
                    print(warning(f"   ⚠️  Found {report.issues_found} issue(s)"))
                    if mode == 'heal' and report.issues_fixed > 0:
                        print(success(f"   ✅ Fixed {report.issues_fixed} issue(s)"))
                else:
                    print(success(f"   ✅ No issues ({report.execution_time:.2f}s)"))
            elif not self.quiet:
                # Normal mode - just show summary
                if report.has_errors:
                    print(error(f"   ❌ Failed"))
                elif report.issues_found > 0:
                    if mode == 'heal' and report.issues_fixed > 0:
                        fixed_pct = (report.issues_fixed / report.issues_found) * 100
                        print(success(f"   ✅ Fixed {report.issues_fixed}/{report.issues_found} ({fixed_pct:.0f}%)"))
                    else:
                        print(warning(f"   ⚠️  {report.issues_found} issue(s)"))
                else:
                    print(success(f"   ✅ Clean"))

            # Stop on error if not continue_on_error
            if not self.continue_on_error and report.has_errors:
                if not self.quiet:
                    print(warning(f"\n⚠️  Stopping due to error in {healer_name}"))
                    print(info("   Run with --continue-on-error to keep going"))
                break

        # Create unified report
        total_execution_time = time.time() - start_time

        return UnifiedReport(
            timestamp=datetime.now().isoformat(),
            mode=mode,
            total_issues_found=sum(r.issues_found for r in reports),
            total_issues_fixed=sum(r.issues_fixed for r in reports),
            healer_reports=reports,
            execution_time=total_execution_time,
            config_path=str(self.config_path) if self.config_path else "unknown"
        )

    def list_healers(self) -> str:
        """
        List all available healers in execution order.

        Returns:
            Formatted string listing healers
        """
        lines = ["Healer execution order:\n"]

        for i, healer_name in enumerate(self.healer_order, 1):
            if healer_name in self.available_healers:
                status = "✅ enabled"
            else:
                status = "❌ disabled"

            lines.append(f"  {i}. {healer_name} {status}\n")

        return ''.join(lines)


class ParallelHealingOrchestrator(HealingOrchestrator):
    """
    Parallel healing orchestrator for improved performance.

    Runs independent healers in parallel while respecting dependencies.
    Uses ThreadPoolExecutor for I/O-bound healers.

    Performance:
    - Independent healers (fix_broken_links, detect_staleness, manage_collapsed)
      run in parallel
    - Dependent healers (sync_canonical, resolve_duplicates, balance_references,
      enforce_disclosure) run sequentially

    Thread safety:
    - Each healer operates on different files (no shared state)
    - Reports are collected after all parallel tasks complete
    """

    # Healers that can run in parallel (no interdependencies)
    PARALLEL_HEALERS = {
        'fix_broken_links',
        'detect_staleness',
        'manage_collapsed',
    }

    # Healers that must run sequentially (have dependencies or modify shared state)
    SEQUENTIAL_HEALERS = {
        'sync_canonical',       # Runs first (updates source data)
        'resolve_duplicates',   # Modifies file content
        'balance_references',   # Depends on link analysis
        'enforce_disclosure',   # Final checks
    }

    def __init__(
        self,
        config: Dict,
        config_path: Optional[Path] = None,
        skip_healers: Optional[List[str]] = None,
        only_healer: Optional[str] = None,
        min_confidence: Optional[float] = None,
        continue_on_error: bool = False,
        verbose: bool = False,
        quiet: bool = False,
        max_workers: Optional[int] = None
    ):
        """
        Initialize parallel orchestrator.

        Args:
            config: Configuration dictionary
            config_path: Path to config file (for reporting)
            skip_healers: List of healer names to skip
            only_healer: Run only this healer
            min_confidence: Override confidence threshold
            continue_on_error: Continue running even if a healer fails
            verbose: Show detailed progress
            quiet: Minimal output (errors only)
            max_workers: Max parallel workers (default: min(cpu_count, 4))
        """
        super().__init__(
            config=config,
            config_path=config_path,
            skip_healers=skip_healers,
            only_healer=only_healer,
            min_confidence=min_confidence,
            continue_on_error=continue_on_error,
            verbose=verbose,
            quiet=quiet
        )

        # Set max workers
        if max_workers is None:
            max_workers = min(cpu_count(), 4)
        self.max_workers = max_workers

    def run_all(self, mode: str = 'check') -> UnifiedReport:
        """
        Run all enabled healing systems with parallel execution where safe.

        Execution order:
        1. sync_canonical (sequential, first)
        2. Parallel batch: fix_broken_links, detect_staleness, manage_collapsed
        3. Sequential batch: resolve_duplicates, balance_references, enforce_disclosure

        Args:
            mode: 'check' or 'heal'

        Returns:
            UnifiedReport with aggregated results
        """
        start_time = time.time()
        reports: List[HealingReport] = []

        if self.verbose:
            print(f"🔧 Running documentation healing systems ({mode} mode, parallel)...\n")

        # Determine which healers to run
        if self.only_healer:
            # Single healer mode - run sequentially
            return super().run_all(mode)

        healers_to_run = [
            name for name in self.healer_order
            if name in self.available_healers
        ]

        # Phase 1: Run sync_canonical first (always sequential)
        if 'sync_canonical' in healers_to_run:
            if self.verbose:
                print(f"▶️  Running sync_canonical (phase 1)...")
            report = self.run_healer('sync_canonical', mode)
            reports.append(report)
            self._print_healer_result(report, mode)

            if not self.continue_on_error and report.has_errors:
                return self._create_report(reports, start_time, mode)

        # Phase 2: Run parallel healers
        parallel_healers = [
            h for h in healers_to_run
            if h in self.PARALLEL_HEALERS
        ]

        if parallel_healers:
            if self.verbose:
                print(f"\n▶️  Running parallel healers (phase 2): {', '.join(parallel_healers)}...")

            parallel_reports = self._run_parallel(parallel_healers, mode)
            reports.extend(parallel_reports)

            # Check for errors
            if not self.continue_on_error:
                for report in parallel_reports:
                    if report.has_errors:
                        if self.verbose:
                            print(f"\n⚠️  Stopping due to error in {report.healer_name}")
                        return self._create_report(reports, start_time, mode)

        # Phase 3: Run sequential healers
        sequential_healers = [
            h for h in healers_to_run
            if h in self.SEQUENTIAL_HEALERS and h != 'sync_canonical'
        ]

        if sequential_healers:
            if self.verbose:
                print(f"\n▶️  Running sequential healers (phase 3)...")

            for healer_name in sequential_healers:
                global _shutdown_requested
                if _shutdown_requested:
                    if self.verbose:
                        print(f"\n⚠️  Shutdown requested, stopping")
                    break

                if self.verbose:
                    print(f"▶️  Running {healer_name}...")

                report = self.run_healer(healer_name, mode)
                reports.append(report)
                self._print_healer_result(report, mode)

                if not self.continue_on_error and report.has_errors:
                    break

        return self._create_report(reports, start_time, mode)

    def _run_parallel(self, healer_names: List[str], mode: str) -> List[HealingReport]:
        """
        Run healers in parallel using ThreadPoolExecutor.

        Args:
            healer_names: List of healer names to run
            mode: 'check' or 'heal'

        Returns:
            List of HealingReport objects
        """
        reports: List[HealingReport] = []

        # Use ThreadPoolExecutor for I/O-bound healers
        # (ProcessPoolExecutor has pickle issues with complex objects)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all healers
            future_to_healer = {
                executor.submit(self.run_healer, name, mode): name
                for name in healer_names
            }

            # Collect results as they complete
            for future in as_completed(future_to_healer):
                healer_name = future_to_healer[future]
                try:
                    report = future.result()
                    reports.append(report)
                    self._print_healer_result(report, mode)
                except Exception as e:
                    # Create error report for failed healer
                    report = HealingReport(
                        healer_name=healer_name,
                        mode=mode,
                        timestamp=datetime.now().isoformat(),
                        issues_found=0,
                        issues_fixed=0,
                        errors=[f"Parallel execution failed: {str(e)}"],
                        execution_time=0.0
                    )
                    reports.append(report)
                    if self.verbose:
                        print(f"   ❌ {healer_name} failed: {e}")

        return reports

    def _print_healer_result(self, report: HealingReport, mode: str):
        """Print healer result if verbose."""
        if not self.verbose:
            return

        if report.has_errors:
            print(f"   ❌ {report.healer_name}: Failed - {report.errors}")
        elif report.issues_found > 0:
            print(f"   ⚠️  {report.healer_name}: Found {report.issues_found} issues")
            if mode == 'heal' and report.issues_fixed > 0:
                print(f"   ✅ {report.healer_name}: Fixed {report.issues_fixed} issues")
        else:
            print(f"   ✅ {report.healer_name}: No issues ({report.execution_time:.2f}s)")

    def _create_report(
        self,
        reports: List[HealingReport],
        start_time: float,
        mode: str
    ) -> UnifiedReport:
        """Create unified report from individual healer reports."""
        return UnifiedReport(
            timestamp=datetime.now().isoformat(),
            mode=mode,
            total_issues_found=sum(r.issues_found for r in reports),
            total_issues_fixed=sum(r.issues_fixed for r in reports),
            healer_reports=reports,
            execution_time=time.time() - start_time,
            config_path=str(self.config_path) if self.config_path else "unknown"
        )


def load_config(config_path: Path, validate: bool = False) -> Dict:
    """
    Load configuration from YAML or TOML file.

    Args:
        config_path: Path to config file
        validate: If True, run full validation (use load_config_validated instead)

    Returns:
        Configuration dictionary

    Raises:
        ValueError: If file format is not supported or file doesn't exist
    """
    if not config_path.exists():
        raise ValueError(f"Config file not found: {config_path}")

    suffix = config_path.suffix.lower()

    if suffix in ['.yaml', '.yml']:
        if not YAML_AVAILABLE:
            raise ValueError("YAML support not available. Install PyYAML: pip install pyyaml")

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

    elif suffix == '.toml':
        if not TOML_AVAILABLE:
            raise ValueError("TOML support not available. Install toml: pip install toml")

        with open(config_path, 'rb') as f:
            config = tomllib.load(f)

    else:
        raise ValueError(f"Unsupported config format: {suffix}. Use .yaml, .yml, or .toml")

    return config


def load_config_validated(config_path: Path) -> Tuple[Dict, ValidationResult]:
    """
    Load and validate configuration file.

    This is the preferred method for loading configs as it:
    1. Checks file format and existence
    2. Parses the config file
    3. Validates all settings (paths, thresholds, patterns, etc.)
    4. Returns both config and validation result

    Args:
        config_path: Path to config file (YAML, TOML, or JSON)

    Returns:
        Tuple of (config_dict, validation_result)

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config format is unsupported

    Example:
        config, result = load_config_validated(Path("config.toml"))
        if not result.is_valid:
            for error in result.errors:
                print(f"Error: {error}")
            sys.exit(1)
        for warning in result.warnings:
            print(f"Warning: {warning}")
    """
    return validate_and_load_config(config_path)


def print_summary_box(unified_report: UnifiedReport):
    """
    Print enhanced summary box with color and formatting.

    Args:
        unified_report: UnifiedReport instance
    """
    lines = []

    # Add healer results
    for report in unified_report.healer_reports:
        if report.has_errors:
            status = error("❌")
            name = report.healer_name.replace('_', ' ').title()
            result = error("Failed")
            lines.append(f"  {status} {name:30} {result}")
        elif report.issues_found == 0:
            status = success("✓")
            name = report.healer_name.replace('_', ' ').title()
            result = success("Clean")
            lines.append(f"  {status} {name:30} {result}")
        else:
            fixed_pct = int((report.issues_fixed / report.issues_found) * 100) if report.issues_found > 0 else 0
            if fixed_pct == 100:
                status = success("✓")
            elif fixed_pct >= 50:
                status = warning("⚠")
            else:
                status = error("⚠")

            name = report.healer_name.replace('_', ' ').title()
            result = f"{report.issues_fixed}/{report.issues_found} issues fixed ({fixed_pct}%)"

            if fixed_pct == 100:
                result = success(result)
            elif fixed_pct >= 50:
                result = warning(result)
            else:
                result = error(result)

            lines.append(f"  {status} {name:30} {result}")

    # Add blank line
    lines.append("")

    # Add totals
    if unified_report.total_issues_found == 0:
        lines.append(success(f"  Total: {unified_report.total_issues_found} issues found"))
    else:
        lines.append(f"  Total: {unified_report.total_issues_found} issues found, {unified_report.total_issues_fixed} fixed")

    lines.append(info(f"  Execution time: {unified_report.execution_time:.1f} seconds"))

    print_box(lines, title="Doc Guardian Summary", width=70)


def generate_markdown_report(unified_report: UnifiedReport) -> str:
    """
    Generate markdown report from unified results.

    Args:
        unified_report: UnifiedReport instance

    Returns:
        Markdown formatted report string
    """
    lines = ["# Documentation Healing Report\n\n"]

    # Metadata
    lines.append(f"**Mode**: {unified_report.mode}\n")
    lines.append(f"**Timestamp**: {unified_report.timestamp}\n")
    lines.append(f"**Config**: {unified_report.config_path}\n")
    lines.append(f"**Execution Time**: {unified_report.execution_time:.2f}s\n\n")

    # Summary
    lines.append("## Summary\n\n")
    lines.append(f"- **Healers Run**: {len(unified_report.healer_reports)}\n")
    lines.append(f"- **Total Issues Found**: {unified_report.total_issues_found}\n")
    lines.append(f"- **Total Issues Fixed**: {unified_report.total_issues_fixed}\n")
    lines.append(f"- **Success Rate**: {unified_report.success_rate*100:.1f}%\n\n")

    if unified_report.total_issues_found == 0:
        lines.append("✅ **All documentation is healthy!**\n\n")

    # Individual healer results
    lines.append("## Healer Results\n\n")

    for report in unified_report.healer_reports:
        status = "❌" if report.has_errors else "✅" if report.issues_found == 0 else "⚠️"
        lines.append(f"### {status} {report.healer_name.replace('_', ' ').title()}\n\n")

        if report.has_errors:
            lines.append("- **Status**: ❌ Failed\n")
            for error in report.errors:
                lines.append(f"- **Error**: {error}\n")
        elif report.issues_found == 0:
            lines.append("- **Status**: ✅ Healthy\n")
        else:
            lines.append("- **Status**: ⚠️ Issues detected\n")
            lines.append(f"- **Issues Found**: {report.issues_found}\n")
            lines.append(f"- **Issues Fixed**: {report.issues_fixed}\n")
            lines.append(f"- **Success Rate**: {report.success_rate*100:.1f}%\n")

        lines.append(f"- **Execution Time**: {report.execution_time:.2f}s\n\n")

    # Recommendations
    if unified_report.mode == 'check' and unified_report.total_issues_found > 0:
        lines.append("## Recommendations\n\n")
        lines.append("Run with `--heal` to auto-fix high-confidence issues:\n\n")
        lines.append("```bash\n")
        lines.append(f"python heal.py --config {unified_report.config_path} --heal\n")
        lines.append("```\n\n")

    if unified_report.mode == 'heal' and (unified_report.total_issues_found - unified_report.total_issues_fixed) > 0:
        lines.append("## Manual Review Required\n\n")
        lines.append(f"Some issues ({unified_report.total_issues_found - unified_report.total_issues_fixed}) require manual attention.\n\n")

    return ''.join(lines)


def main():
    """Main CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Universal documentation healing orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --config config.yaml --list
  %(prog)s --config config.yaml --check
  %(prog)s --config config.yaml --heal
  %(prog)s --config config.yaml --heal --only fix_broken_links
  %(prog)s --config config.yaml --heal --skip enforce_disclosure
  %(prog)s --config config.yaml --heal --min-confidence 0.95
        """
    )

    parser.add_argument(
        '--config',
        type=Path,
        required=True,
        help='Path to configuration file (YAML or TOML)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all healers in execution order and exit'
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help='Check all healers (default mode)'
    )

    parser.add_argument(
        '--heal',
        action='store_true',
        help='Auto-heal high-confidence issues'
    )

    parser.add_argument(
        '--skip',
        help='Comma-separated list of healers to skip'
    )

    parser.add_argument(
        '--only',
        help='Run only this healer'
    )

    parser.add_argument(
        '--min-confidence',
        type=float,
        help='Minimum confidence for auto-healing (default: from config)'
    )

    parser.add_argument(
        '--continue-on-error',
        action='store_true',
        help='Continue running healers even if one fails'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output (implies debug info)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output (errors only, no progress)'
    )

    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Run independent healers in parallel (faster for large codebases)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=None,
        help='Max parallel workers (default: min(cpu_count, 4))'
    )

    parser.add_argument(
        '--strict',
        action='store_true',
        help='Exit with code 1 if any issues found (for CI/CD)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        help='Path to write report (default: from config or stdout only)'
    )

    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate config, do not run healers'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    # Load and validate configuration using comprehensive validator
    # This addresses all 8 CRITICAL issues from CONFIG_VALIDATION_AUDIT.md
    try:
        config, validation_result = load_config_validated(args.config)
    except FileNotFoundError as e:
        print(f"ERROR: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: Failed to load config: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error loading config: {e}", file=sys.stderr)
        sys.exit(1)

    # Print validation warnings (unless quiet mode)
    if not args.quiet:
        for warning in validation_result.warnings:
            print(f"Warning: {warning}", file=sys.stderr)

    # Print validation errors and exit if invalid
    if not validation_result.is_valid:
        print(f"\nERROR: Configuration validation failed with {len(validation_result.errors)} error(s):", file=sys.stderr)
        for err_msg in validation_result.errors[:20]:  # Show first 20 errors
            print(f"   - {err_msg}", file=sys.stderr)
        if len(validation_result.errors) > 20:
            print(f"   ... and {len(validation_result.errors) - 20} more errors", file=sys.stderr)
        print(f"\nFix the above errors and re-run. See CONFIG_VALIDATION_AUDIT.md for details.", file=sys.stderr)
        sys.exit(1)

    # Exit if validate-only mode
    if args.validate_only:
        if validation_result.warnings:
            print(f"OK: Configuration is valid (with {len(validation_result.warnings)} warning(s))")
        else:
            print("OK: Configuration is valid")
        sys.exit(0)

    # Parse skip list
    skip_healers = args.skip.split(',') if args.skip else []

    # Validate verbosity flags
    if args.verbose and args.quiet:
        from guardian.core.colors import error as color_error
        print(color_error("ERROR: --verbose and --quiet are mutually exclusive"), file=sys.stderr)
        sys.exit(1)

    # Create orchestrator (parallel or sequential)
    if args.parallel:
        orchestrator = ParallelHealingOrchestrator(
            config=config,
            config_path=args.config,
            skip_healers=skip_healers,
            only_healer=args.only,
            min_confidence=args.min_confidence,
            continue_on_error=args.continue_on_error,
            verbose=args.verbose,
            quiet=args.quiet,
            max_workers=args.max_workers
        )
    else:
        orchestrator = HealingOrchestrator(
            config=config,
            config_path=args.config,
            skip_healers=skip_healers,
            only_healer=args.only,
            min_confidence=args.min_confidence,
            continue_on_error=args.continue_on_error,
            verbose=args.verbose,
            quiet=args.quiet
        )

    # Handle --list flag
    if args.list:
        print(orchestrator.list_healers())
        sys.exit(0)

    # Determine mode
    # --dry-run forces check mode (shows what would be done without changes)
    if args.dry_run:
        mode = 'check'
        if args.verbose:
            print("[DRY RUN] Showing proposed changes without modifying files\n")
    else:
        mode = 'heal' if args.heal else 'check'

    # Run all healers
    unified_report = orchestrator.run_all(mode=mode)

    # Print summary box (unless quiet mode)
    if not args.quiet:
        print()  # Add blank line
        print_summary_box(unified_report)

    # Generate markdown report (always generate for file output, conditionally print)
    report_markdown = generate_markdown_report(unified_report)

    # Only print full markdown if verbose or if saving to file
    if args.verbose:
        print("\n" + report_markdown)

    # Save report if requested or configured
    output_path = args.output
    if not output_path:
        # Get from config
        reporting_config = config.get('reporting', {})
        output_dir = reporting_config.get('output_dir')
        if output_dir:
            output_path = Path(output_dir) / 'healing_report.md'

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report_markdown)
        if not args.quiet:
            print(success(f"📄 Report saved to {output_path}"))

    # Exit code for strict mode
    if args.strict and unified_report.total_issues_found > 0:
        if not args.quiet:
            print(error(f"\n❌ Strict mode: Found {unified_report.total_issues_found} issue(s)"))
        sys.exit(1)

    # Exit code for errors
    if unified_report.has_errors and not args.continue_on_error:
        if not args.quiet:
            print(error(f"\n❌ Healing failed with errors"))
        sys.exit(1)

    # Success message
    if not args.quiet and unified_report.total_issues_found == 0:
        print(success("\n✨ All documentation is healthy!"))

    sys.exit(0)


if __name__ == "__main__":
    main()
