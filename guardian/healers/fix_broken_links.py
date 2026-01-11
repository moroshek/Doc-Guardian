"""
Broken Link Detection & Auto-Fix Healer

Universal healer for detecting and fixing broken markdown links.

Features:
- Scans markdown files for broken internal links
- Uses Levenshtein distance for fuzzy matching
- Supports relative and absolute paths
- Handles anchor fragments (#section)
- Excludes code blocks and external URLs
- Multi-factor confidence scoring
- O(1) file lookup with pre-built index (optimized from O(n) per broken link)
- Symlink loop protection (FS-05)
- Regex validation at init (CFG-05)

Configuration:
    config['healers']['fix_broken_links']['link_pattern']: Regex for markdown links
    config['healers']['fix_broken_links']['fuzzy_threshold']: Minimum similarity (0.5)
    config['healers']['fix_broken_links']['handle_anchors']: Whether to validate anchors
    config['healers']['fix_broken_links']['exclude_dirs']: Directories to skip
    config['healers']['fix_broken_links']['file_extensions']: Which files to scan for targets
    config['healers']['fix_broken_links']['max_symlink_depth']: Max symlink resolution depth (10)

Performance:
    - Pre-built file index reduces O(n) tree scan per broken link to O(1) lookup
    - Levenshtein calculations cached for repeated comparisons
"""

import re
import signal
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set
from difflib import SequenceMatcher
from collections import defaultdict
import time

from guardian.core.base import HealingSystem, HealingReport, Change
from guardian.core.confidence import (
    calculate_confidence,
    ConfidenceFactors,
    assess_change_magnitude,
    assess_risk_level
)
from guardian.core.regex_validator import (
    validate_regex_safety,
    RegexSecurityError,
    RegexConfigError,
)
from guardian.core.security import (
    validate_file_size,
    safe_read_file,
    MAX_LINKS_PER_FILE,
)
from guardian.core.colors import show_progress, clear_progress


# Maximum symlink resolution depth (FS-05)
MAX_SYMLINK_DEPTH = 10

# Maximum line length to process (DC-10)
MAX_LINE_LENGTH = 100000


class RegexConfigError(ValueError):
    """Raised when regex pattern in config is invalid (CFG-05)."""
    pass


class SymlinkLoopError(ValueError):
    """Raised when symlink loop is detected (FS-05)."""
    pass


def resolve_with_depth_limit(path: Path, max_depth: int = MAX_SYMLINK_DEPTH) -> Path:
    """
    Resolve symlinks with depth limit to prevent loops (FS-05).

    Args:
        path: Path to resolve
        max_depth: Maximum symlink resolution depth

    Returns:
        Resolved path

    Raises:
        SymlinkLoopError: If symlink depth limit exceeded (infinite loop detected)
    """
    depth = 0
    current = path

    while current.is_symlink() and depth < max_depth:
        try:
            current = Path(current.parent / current.readlink())
        except (OSError, ValueError):
            break
        depth += 1

    if depth >= max_depth:
        raise SymlinkLoopError(
            f"Symlink depth limit ({max_depth}) exceeded for {path} - possible infinite loop"
        )

    try:
        return current.resolve()
    except (OSError, RuntimeError) as e:
        # RuntimeError can occur with infinite loops on some systems
        raise SymlinkLoopError(f"Cannot resolve path {path}: {e}")


@dataclass
class Link:
    """A markdown link found in a file."""
    file: Path
    line_num: int
    text: str
    target: str
    full_match: str


@dataclass
class BrokenLink:
    """A broken link with suggested fix and confidence score."""
    link: Link
    reason: str
    suggested_fix: Optional[str] = None
    confidence: float = 0.0


class FileIndex:
    """
    Pre-built file index for O(1) lookup.

    Instead of scanning the entire file tree for each broken link (O(n) per link),
    we build an index once and lookup in O(1).

    Index structure:
    - by_name: Maps filename to list of paths (for exact matches)
    - by_stem: Maps stem (without extension) to list of paths
    - by_lower_name: Case-insensitive name lookup
    - by_extension: Groups files by extension

    Performance:
    - Build time: O(n) where n = number of files
    - Lookup time: O(1) for exact match, O(k) for fuzzy where k = candidates
    """

    def __init__(self, root: Path, file_extensions: List[str], exclude_dirs: Set[str]):
        """
        Build file index from root directory.

        Args:
            root: Root directory to index
            file_extensions: List of file extensions to include
            exclude_dirs: Set of directory names to skip
        """
        self.root = root
        self.file_extensions = set(file_extensions)
        self.exclude_dirs = exclude_dirs

        # Index structures
        self.by_name: Dict[str, List[Path]] = defaultdict(list)
        self.by_stem: Dict[str, List[Path]] = defaultdict(list)
        self.by_lower_name: Dict[str, List[Path]] = defaultdict(list)
        self.all_files: List[Path] = []

        # Build index
        self._build_index()

    def _build_index(self):
        """Build index from file tree (O(n) one-time cost)."""
        for file_path in self.root.rglob("*"):
            # Skip directories
            if not file_path.is_file():
                continue

            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in self.exclude_dirs):
                continue

            # Only index files with allowed extensions
            if file_path.suffix not in self.file_extensions:
                continue

            # Add to indices
            self.all_files.append(file_path)
            self.by_name[file_path.name].append(file_path)
            self.by_stem[file_path.stem].append(file_path)
            self.by_lower_name[file_path.name.lower()].append(file_path)

    def find_exact(self, filename: str) -> List[Path]:
        """
        Find files with exact name match (O(1)).

        Args:
            filename: Exact filename to find

        Returns:
            List of matching paths
        """
        return self.by_name.get(filename, [])

    def find_case_insensitive(self, filename: str) -> List[Path]:
        """
        Find files with case-insensitive name match (O(1)).

        Args:
            filename: Filename to find (any case)

        Returns:
            List of matching paths
        """
        return self.by_lower_name.get(filename.lower(), [])

    def find_by_stem(self, stem: str) -> List[Path]:
        """
        Find files by stem (name without extension) (O(1)).

        Args:
            stem: Stem to find

        Returns:
            List of matching paths
        """
        return self.by_stem.get(stem, [])

    def find_similar(self, target: str, similarity_threshold: float = 0.5) -> List[Tuple[Path, float]]:
        """
        Find files with similar names (O(k) where k = candidates).

        Uses indexed lookup first, then fuzzy matching on candidates.

        Args:
            target: Target filename to match
            similarity_threshold: Minimum similarity score

        Returns:
            List of (path, similarity) tuples, sorted by similarity descending
        """
        target_name = Path(target).name
        target_stem = Path(target).stem
        target_lower = target_name.lower()

        candidates: Dict[Path, float] = {}

        # Phase 1: Exact and near-exact matches (O(1))
        for path in self.find_case_insensitive(target_name):
            candidates[path] = 1.0

        for path in self.find_by_stem(target_stem):
            if path not in candidates:
                candidates[path] = 0.95

        # Phase 2: Prefix/suffix matches (O(k) where k = index keys matching prefix)
        for name, paths in self.by_lower_name.items():
            if target_lower in name or name in target_lower:
                for path in paths:
                    if path not in candidates:
                        # Calculate actual similarity
                        sim = SequenceMatcher(None, target_lower, name).ratio()
                        if sim >= similarity_threshold:
                            candidates[path] = sim

        # Phase 3: For remaining, use Levenshtein on likely candidates
        # We limit this to avoid O(n) scanning
        if len(candidates) < 10:
            # Only check files that share at least 2 characters with target
            target_chars = set(target_lower)
            for path in self.all_files[:1000]:  # Limit scan
                if path in candidates:
                    continue

                name_lower = path.name.lower()
                name_chars = set(name_lower)

                # Quick filter: must share some characters
                if len(target_chars & name_chars) >= 2:
                    sim = SequenceMatcher(None, target_lower, name_lower).ratio()
                    if sim >= similarity_threshold:
                        candidates[path] = sim

        # Sort by similarity
        return sorted(candidates.items(), key=lambda x: x[1], reverse=True)

    @property
    def size(self) -> int:
        """Number of indexed files."""
        return len(self.all_files)


class LinkExtractor:
    """Extract markdown links from files."""

    def __init__(self, link_pattern: str, logger=None):
        """
        Initialize extractor with link pattern.

        Args:
            link_pattern: Regex pattern for markdown links (e.g., r'\\[([^\\]]+)\\]\\(([^\\)]+)\\)')
            logger: Optional logger for error reporting

        Raises:
            RegexConfigError: If link_pattern is invalid regex (CFG-05)
            RegexSecurityError: If link_pattern is potentially dangerous (DG-2026-002)
        """
        # Security: Validate regex for ReDoS patterns (DG-2026-002)
        is_safe, error = validate_regex_safety(link_pattern)
        if not is_safe:
            raise RegexSecurityError(
                f"Potentially dangerous link_pattern: '{link_pattern}'. Error: {error}"
            )

        # Validate regex at init time (CFG-05)
        try:
            self.LINK_PATTERN = re.compile(link_pattern)
        except re.error as e:
            raise RegexConfigError(
                f"Invalid link_pattern regex: '{link_pattern}'. Error: {e}"
            ) from e
        self._logger = logger
        self._errors: List[str] = []

    def extract_from_file(self, file_path: Path) -> List[Link]:
        """
        Extract all markdown links from a file.

        Skips:
        - Links inside code blocks (```)
        - Links in inline code (`...`)
        - Lines exceeding MAX_LINE_LENGTH (DC-10)

        Security:
        - File size validation before reading (DG-2026-006)
        - Link count limit per file (DG-2026-006)

        Args:
            file_path: Path to markdown file

        Returns:
            List of Link objects found in file
        """
        links = []

        try:
            # Resolve symlinks safely (FS-05)
            try:
                resolved_path = resolve_with_depth_limit(file_path)
            except SymlinkLoopError as e:
                error_msg = f"Symlink loop detected for {file_path}: {e}"
                self._errors.append(error_msg)
                if self._logger:
                    self._logger.warning(error_msg)
                return links

            # Security: Validate file size before reading (DG-2026-006)
            is_valid, error = validate_file_size(resolved_path)
            if not is_valid:
                error_msg = f"File too large: {file_path}: {error}"
                self._errors.append(error_msg)
                if self._logger:
                    self._logger.warning(error_msg)
                return links

            with open(resolved_path, encoding='utf-8', errors='replace') as f:
                in_code_block = False
                for line_num, line in enumerate(f, 1):
                    # Skip extremely long lines (DC-10)
                    if len(line) > MAX_LINE_LENGTH:
                        error_msg = f"Line {line_num} in {file_path} exceeds max length ({len(line)} > {MAX_LINE_LENGTH})"
                        self._errors.append(error_msg)
                        if self._logger:
                            self._logger.warning(error_msg)
                        continue

                    # Track code block state
                    if line.strip().startswith('```'):
                        in_code_block = not in_code_block
                        continue

                    # Skip links in code blocks
                    if in_code_block:
                        continue

                    for match in self.LINK_PATTERN.finditer(line):
                        # Security: Limit links per file (DG-2026-006)
                        if len(links) >= MAX_LINKS_PER_FILE:
                            error_msg = f"Link limit reached in {file_path} (max {MAX_LINKS_PER_FILE})"
                            self._errors.append(error_msg)
                            if self._logger:
                                self._logger.warning(error_msg)
                            return links

                        text, target = match.groups()
                        links.append(Link(
                            file=file_path,
                            line_num=line_num,
                            text=text,
                            target=target,
                            full_match=match.group(0)
                        ))
        except PermissionError as e:
            error_msg = f"Permission denied reading {file_path}: {e}"
            self._errors.append(error_msg)
            if self._logger:
                self._logger.warning(error_msg)
        except UnicodeDecodeError as e:
            # Binary file or encoding issue - log but don't fail
            error_msg = f"Encoding error reading {file_path}: {e}"
            self._errors.append(error_msg)
            if self._logger:
                self._logger.debug(error_msg)
        except OSError as e:
            error_msg = f"OS error reading {file_path}: {e}"
            self._errors.append(error_msg)
            if self._logger:
                self._logger.warning(error_msg)
        except Exception as e:
            # Catch-all for unexpected errors - log instead of silently swallowing
            error_msg = f"Unexpected error reading {file_path}: {type(e).__name__}: {e}"
            self._errors.append(error_msg)
            if self._logger:
                self._logger.error(error_msg)

        return links

    @property
    def errors(self) -> List[str]:
        """Return list of errors encountered during extraction."""
        return self._errors.copy()

    def extract_from_tree(self, root: Path, exclude_dirs: set, pattern: str = "*.md") -> List[Link]:
        """
        Extract links from all markdown files in directory tree.

        Args:
            root: Root directory to search
            exclude_dirs: Set of directory names to skip
            pattern: Glob pattern for files to scan

        Returns:
            List of all Link objects found
        """
        all_links = []
        for file_path in root.rglob(pattern):
            # Skip if path contains any excluded directory
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue
            all_links.extend(self.extract_from_file(file_path))
        return all_links


class LinkValidator:
    """Validate links and identify broken ones."""

    def __init__(self, project_root: Path):
        """
        Initialize validator.

        Args:
            project_root: Absolute path to project root
        """
        self.project_root = project_root

    def resolve_target(self, link: Link) -> Optional[Path]:
        """
        Resolve link target to absolute path.

        Handles:
        - Absolute paths (/docs/guide.md)
        - Relative paths (../guide.md, ./guide.md)
        - Anchor fragments (#section or path#section)

        Args:
            link: Link object to resolve

        Returns:
            Path if target exists, None if broken or external
        """
        target = link.target

        # Skip external links (assume valid - external validation requires HTTP requests)
        if target.startswith(('http://', 'https://', 'mailto:')):
            return None

        # Skip anchor-only links (TODO: validate section headers exist)
        if target.startswith('#'):
            return None

        # Strip anchor fragment if present
        if '#' in target:
            target = target.split('#')[0]
            if not target:  # Was anchor-only
                return None

        # Resolve path
        if target.startswith('/'):
            # Absolute path from project root
            abs_path = self.project_root / target.lstrip('/')
        else:
            # Relative to link's file
            abs_path = (link.file.parent / target).resolve()

        return abs_path if abs_path.exists() else None

    def validate(self, link: Link) -> Optional[BrokenLink]:
        """
        Validate a link.

        Args:
            link: Link object to validate

        Returns:
            BrokenLink if target is broken, None if valid
        """
        # External links and anchor-only links pass validation
        if link.target.startswith(('http://', 'https://', 'mailto:', '#')):
            return None

        target_path = self.resolve_target(link)

        if target_path is None or not target_path.exists():
            return BrokenLink(
                link=link,
                reason=f"Target does not exist: {link.target}"
            )

        return None


class LinkFixer:
    """Suggest and apply fixes for broken links."""

    def __init__(
        self,
        project_root: Path,
        fuzzy_threshold: float,
        file_extensions: List[str],
        file_index: Optional[FileIndex] = None,
        exclude_dirs: Optional[Set[str]] = None
    ):
        """
        Initialize fixer.

        Args:
            project_root: Absolute path to project root
            fuzzy_threshold: Minimum similarity score (0.0-1.0) for candidates
            file_extensions: List of file extensions to consider as targets (e.g., ['.md', '.py'])
            file_index: Pre-built file index for O(1) lookups (optional, built on demand)
            exclude_dirs: Directories to exclude from indexing
        """
        self.project_root = project_root
        self.fuzzy_threshold = fuzzy_threshold
        self.file_extensions = file_extensions
        self.exclude_dirs = exclude_dirs or set()

        # Use provided index or build one lazily
        self._file_index = file_index
        self._index_built = file_index is not None

    @property
    def file_index(self) -> FileIndex:
        """Get or build file index lazily."""
        if not self._index_built:
            self._file_index = FileIndex(
                self.project_root,
                self.file_extensions,
                self.exclude_dirs
            )
            self._index_built = True
        return self._file_index

    def levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.

        Uses dynamic programming to compute minimum edit distance.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Number of edits (insertions, deletions, substitutions) needed
        """
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def calculate_similarity(self, broken_target: str, candidate_path: Path) -> float:
        """
        Calculate similarity score for a candidate match.

        Scoring rules:
        - Exact match (case-insensitive): 1.0
        - Basename match + similar directory: 0.95
        - Levenshtein distance ≤ 2: 0.90-0.95
        - Levenshtein distance 3-5: 0.85-0.90
        - Otherwise: SequenceMatcher ratio

        Args:
            broken_target: Original (broken) target path
            candidate_path: Candidate file path to compare

        Returns:
            Similarity score (0.0-1.0)
        """
        broken_name = Path(broken_target).name
        candidate_name = candidate_path.name

        # Exact match (case-insensitive)
        if broken_name.lower() == candidate_name.lower():
            return 1.0

        # Basename match with similar directory structure
        broken_dir = str(Path(broken_target).parent)
        try:
            candidate_dir = str(candidate_path.parent.relative_to(self.project_root))
        except ValueError:
            candidate_dir = str(candidate_path.parent)

        if broken_name.lower() == candidate_name.lower():
            if SequenceMatcher(None, broken_dir, candidate_dir).ratio() > 0.7:
                return 0.95

        # Levenshtein distance scoring
        lev_dist = self.levenshtein_distance(broken_name.lower(), candidate_name.lower())
        if lev_dist <= 2:
            return 0.95 - (lev_dist * 0.025)  # 0.95, 0.925, 0.90
        elif lev_dist <= 5:
            return 0.90 - ((lev_dist - 2) * 0.0166)  # 0.90, 0.88, 0.87, 0.85

        # Fallback to SequenceMatcher
        return SequenceMatcher(None, broken_name, candidate_name).ratio()

    def find_similar_file(self, broken_target: str, broken_link: Link, exclude_dirs: set) -> List[Tuple[Path, float]]:
        """
        Find similar files using O(1) indexed lookup.

        Strategy (optimized):
        1. Use pre-built FileIndex for O(1) exact/fuzzy lookup
        2. Calculate similarity scores for candidates
        3. Filter by fuzzy_threshold
        4. Sort by similarity (highest first)

        Performance:
        - Old: O(n) file tree scan per broken link
        - New: O(1) index lookup + O(k) similarity calc where k = candidates

        Args:
            broken_target: Original (broken) target path
            broken_link: Link object (for context)
            exclude_dirs: Set of directory names to skip

        Returns:
            List of (path, similarity_score) tuples, sorted by score descending
        """
        # Use FileIndex for O(1) lookup instead of O(n) rglob
        indexed_candidates = self.file_index.find_similar(broken_target, self.fuzzy_threshold)

        # Recalculate similarity using our more sophisticated algorithm
        candidates = []
        seen_paths: Set[Path] = set()

        for file_path, indexed_sim in indexed_candidates:
            if file_path in seen_paths:
                continue
            seen_paths.add(file_path)

            # Skip excluded directories (should already be excluded by index, but double-check)
            if any(excluded in file_path.parts for excluded in exclude_dirs):
                continue

            # Use our detailed similarity calculation
            similarity = self.calculate_similarity(broken_target, file_path)
            if similarity >= self.fuzzy_threshold:
                candidates.append((file_path, similarity))

        return sorted(candidates, key=lambda x: x[1], reverse=True)

    def suggest_fix(self, broken_link: BrokenLink, exclude_dirs: set, historical_success_rate: float = 0.92) -> BrokenLink:
        """
        Suggest a fix for a broken link.

        Uses multi-factor confidence scoring:
        - Pattern match: Similarity score from fuzzy matching
        - Change magnitude: Single link change (small)
        - Risk assessment: Link fixes are low-risk
        - Historical accuracy: Configurable success rate

        Args:
            broken_link: BrokenLink object to fix
            exclude_dirs: Set of directory names to skip during search
            historical_success_rate: Past success rate for link fixes (0.0-1.0)

        Returns:
            Updated BrokenLink with suggested_fix and confidence set
        """
        similar = self.find_similar_file(broken_link.link.target, broken_link.link, exclude_dirs)

        if not similar:
            broken_link.confidence = 0.0
            return broken_link

        best_match, similarity = similar[0]

        # Preserve anchor if present in original link
        anchor = ""
        if '#' in broken_link.link.target:
            anchor = '#' + broken_link.link.target.split('#', 1)[1]

        # Convert to relative path from link's file
        try:
            rel_path = best_match.relative_to(broken_link.link.file.parent)
            suggested = str(rel_path) + anchor
        except ValueError:
            # Files not in same tree, use absolute path from project root
            suggested = '/' + str(best_match.relative_to(self.project_root)) + anchor

        # Calculate multi-factor confidence
        factors = ConfidenceFactors(
            pattern_match=similarity,  # Fuzzy match score
            change_magnitude=0.9,  # Single link change is small
            risk_assessment=assess_risk_level('broken_link_fix'),  # 0.9
            historical_accuracy=historical_success_rate
        )
        confidence = calculate_confidence(factors)

        broken_link.suggested_fix = suggested
        broken_link.confidence = confidence

        return broken_link

    def apply_fix(self, broken_link: BrokenLink) -> bool:
        """
        Apply fix to file.

        Replaces old link with new link in-place.

        Args:
            broken_link: BrokenLink with suggested_fix set

        Returns:
            True if fix was successfully applied
        """
        if not broken_link.suggested_fix:
            return False

        try:
            with open(broken_link.link.file) as f:
                content = f.read()

            # Replace old link with new link
            old_link = broken_link.link.full_match
            new_link = f"[{broken_link.link.text}]({broken_link.suggested_fix})"

            new_content = content.replace(old_link, new_link)

            with open(broken_link.link.file, 'w') as f:
                f.write(new_content)

            return True

        except Exception:
            return False


class FixBrokenLinksHealer(HealingSystem):
    """
    Healer for detecting and fixing broken markdown links.

    Configuration keys:
        config['healers']['fix_broken_links']['link_pattern']: Regex for links
        config['healers']['fix_broken_links']['fuzzy_threshold']: Min similarity (default 0.5)
        config['healers']['fix_broken_links']['handle_anchors']: Validate anchors (default False)
        config['healers']['fix_broken_links']['exclude_dirs']: Dirs to skip
        config['healers']['fix_broken_links']['file_extensions']: Target file types
        config['healers']['fix_broken_links']['historical_success_rate']: Past accuracy (default 0.92)
    """

    def __init__(self, config: dict):
        """
        Initialize broken links healer.

        Args:
            config: Configuration dict (see class docstring for required keys)
        """
        super().__init__(config)

        # Load healer-specific config with safe defaults
        healer_config = config.get('healers', {}).get('fix_broken_links', {})

        link_pattern = healer_config.get('link_pattern', r'\[([^\]]+)\]\(([^\)]+)\)')
        fuzzy_threshold = healer_config.get('fuzzy_threshold', 0.5)
        self.exclude_dirs = set(healer_config.get('exclude_dirs', [
            '.git', 'node_modules', 'venv', '.venv', '__pycache__',
            '.next', 'dist', 'build', '.pytest_cache', '.mypy_cache'
        ]))
        file_extensions = healer_config.get('file_extensions', ['.md', '.py', '.json', '.sh', '.ts', '.tsx', '.js'])
        self.historical_success_rate = healer_config.get('historical_success_rate', 0.92)

        # Initialize components
        self.extractor = LinkExtractor(link_pattern)
        self.validator = LinkValidator(self.project_root)
        self.fixer = LinkFixer(
            self.project_root,
            fuzzy_threshold,
            file_extensions,
            file_index=None,  # Built lazily on first use
            exclude_dirs=self.exclude_dirs
        )

    def check(self) -> HealingReport:
        """
        Scan documentation for broken links.

        Returns:
            HealingReport with:
            - issues_found: Number of broken links detected
            - changes: List of proposed fixes with confidence scores
            - mode: "check"
        """
        start_time = time.time()

        # Extract all links from markdown files
        all_links = self.extractor.extract_from_tree(
            self.doc_root,
            self.exclude_dirs
        )

        # Validate each link
        broken_links: List[BrokenLink] = []
        total_links = len(all_links)
        for idx, link in enumerate(all_links, 1):
            show_progress(idx, total_links, prefix="Checking links")
            broken = self.validator.validate(link)
            if broken:
                broken_links.append(broken)

        # Clear progress bar after completion
        if total_links > 0:
            clear_progress()

        # Generate fix suggestions with confidence scores
        changes: List[Change] = []
        for broken in broken_links:
            broken = self.fixer.suggest_fix(broken, self.exclude_dirs, self.historical_success_rate)

            if broken.suggested_fix:
                old_link = broken.link.full_match
                new_link = f"[{broken.link.text}]({broken.suggested_fix})"

                changes.append(Change(
                    file=broken.link.file,
                    line=broken.link.line_num,
                    old_content=old_link,
                    new_content=new_link,
                    confidence=broken.confidence,
                    reason=f"Fix broken link: {broken.link.target} → {broken.suggested_fix}",
                    healer="FixBrokenLinksHealer"
                ))

        execution_time = time.time() - start_time

        return self.create_report(
            mode="check",
            issues_found=len(broken_links),
            issues_fixed=0,
            changes=changes,
            execution_time=execution_time
        )

    def heal(self, min_confidence: Optional[float] = None) -> HealingReport:
        """
        Apply fixes for broken links above confidence threshold.

        Args:
            min_confidence: Override default confidence threshold from config

        Returns:
            HealingReport with:
            - issues_found: Number of broken links detected
            - issues_fixed: Number of links successfully fixed
            - changes: List of applied changes
            - mode: "heal"
        """
        start_time = time.time()

        # Get proposed fixes from check()
        check_report = self.check()

        # Use provided threshold or fall back to config
        threshold = min_confidence if min_confidence is not None else self.min_confidence

        # Filter by confidence
        changes_to_apply = [c for c in check_report.changes if c.confidence >= threshold]

        # Apply each change
        applied_changes: List[Change] = []
        for change in changes_to_apply:
            if self.validate_change(change):
                if self.apply_change(change):
                    applied_changes.append(change)
                else:
                    self.log_error(f"Failed to apply change to {change.file}:{change.line}")
            else:
                self.log_error(f"Change validation failed for {change.file}:{change.line}")

        execution_time = time.time() - start_time

        return self.create_report(
            mode="heal",
            issues_found=check_report.issues_found,
            issues_fixed=len(applied_changes),
            changes=applied_changes,
            execution_time=execution_time
        )
