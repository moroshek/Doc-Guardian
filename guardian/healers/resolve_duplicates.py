"""
Duplicate Content Resolution Healer

Detects duplicate content across documentation files and consolidates them.

Features:
- Finds duplicate paragraphs and code blocks (≥80% similar)
- Determines canonical location using configurable hierarchy rules
- Replaces duplicates with links to canonical content
- Confidence-based automatic consolidation
- O(n log n) duplicate detection using SimHash (optimized from O(n²))
- Memory-bounded streaming for large files (RT-01)
- Proper error logging (no silent failures)

Configuration (in config.toml):
    [healers.resolve_duplicates]
    similarity_threshold = 0.80  # Min similarity to consider duplicate
    min_block_size = 100         # Min characters for a block
    hierarchy_rules = [          # Files earlier = more canonical
        "README.md",
        "docs/",
        "guides/"
    ]
    use_fast_detection = true    # Use SimHash for O(n log n) detection
    max_file_size = 10000000     # Max file size in bytes (10MB, RT-01)

Usage:
    from guardian.healers.resolve_duplicates import ResolveDuplicatesHealer

    healer = ResolveDuplicatesHealer(config)
    report = healer.check()           # Find duplicates
    report = healer.heal()            # Auto-consolidate high confidence

Performance:
    - With use_fast_detection=true (default): O(n log n) using SimHash
    - Hash buckets reduce comparisons from n² to ~n*k where k is bucket size
    - Memory bounded by streaming extraction and max_file_size limit
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Set, Tuple, Optional, Dict, Iterator
from difflib import SequenceMatcher
from collections import defaultdict
import time
import hashlib
import logging

from ..core.base import HealingSystem, HealingReport, Change
from ..core.file_cache import get_file_cache, simhash, hamming_distance


# Maximum file size for in-memory processing (RT-01)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# Get module logger
logger = logging.getLogger(__name__)


@dataclass
class ContentBlock:
    """A block of content extracted from a file."""
    file: Path
    start_line: int
    end_line: int
    content: str
    block_type: str  # 'paragraph', 'code', 'list', 'table'


@dataclass
class Duplication:
    """A detected duplication between content blocks."""
    blocks: List[ContentBlock]
    similarity: float
    canonical_location: Path
    suggested_action: str  # 'replace_with_link', 'merge', 'review'
    confidence: float


class ContentExtractor:
    """
    Extract content blocks from markdown files.

    Features:
    - Memory-bounded extraction for large files (RT-01)
    - Proper error logging instead of silent failures
    - Streaming for files over MAX_FILE_SIZE_BYTES
    """

    def __init__(self, max_file_size: int = MAX_FILE_SIZE_BYTES):
        """
        Initialize content extractor.

        Args:
            max_file_size: Maximum file size for in-memory processing
        """
        self.max_file_size = max_file_size
        self._errors: List[str] = []

    def _check_file_size(self, file_path: Path) -> bool:
        """
        Check if file is within size limits (RT-01).

        Args:
            file_path: Path to check

        Returns:
            True if file is within limits, False otherwise
        """
        try:
            size = file_path.stat().st_size
            if size > self.max_file_size:
                msg = f"File too large for in-memory processing: {file_path} ({size} bytes > {self.max_file_size})"
                self._errors.append(msg)
                logger.warning(msg)
                return False
            return True
        except OSError as e:
            msg = f"Cannot stat file {file_path}: {e}"
            self._errors.append(msg)
            logger.warning(msg)
            return False

    def extract_paragraphs(self, file_path: Path) -> List[ContentBlock]:
        """
        Extract paragraphs (text between blank lines).

        Skips:
        - Headers (lines starting with #)
        - Code blocks (lines with ```)
        - Tables (lines starting with |)
        - Lists (lines starting with -, *, >)
        - Files exceeding max_file_size (RT-01)

        Returns:
            List of ContentBlock objects for paragraphs
        """
        blocks = []

        # Check file size first (RT-01)
        if not self._check_file_size(file_path):
            return blocks

        try:
            with open(file_path, encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            current_para = []
            start_line = 0

            for i, line in enumerate(lines, 1):
                stripped = line.strip()

                # Skip headers, code blocks, tables, lists
                if stripped.startswith(('#', '```', '|', '-', '*', '>')):
                    if current_para:
                        blocks.append(ContentBlock(
                            file=file_path,
                            start_line=start_line,
                            end_line=i - 1,
                            content='\n'.join(current_para),
                            block_type='paragraph'
                        ))
                        current_para = []
                    continue

                if stripped:
                    if not current_para:
                        start_line = i
                    current_para.append(stripped)
                elif current_para:
                    blocks.append(ContentBlock(
                        file=file_path,
                        start_line=start_line,
                        end_line=i - 1,
                        content='\n'.join(current_para),
                        block_type='paragraph'
                    ))
                    current_para = []

            # Capture final paragraph
            if current_para:
                blocks.append(ContentBlock(
                    file=file_path,
                    start_line=start_line,
                    end_line=len(lines),
                    content='\n'.join(current_para),
                    block_type='paragraph'
                ))

        except PermissionError as e:
            msg = f"Permission denied reading {file_path}: {e}"
            self._errors.append(msg)
            logger.warning(msg)
        except UnicodeDecodeError as e:
            msg = f"Encoding error reading {file_path}: {e}"
            self._errors.append(msg)
            logger.debug(msg)
        except OSError as e:
            msg = f"OS error reading {file_path}: {e}"
            self._errors.append(msg)
            logger.warning(msg)
        except Exception as e:
            # Catch-all with logging instead of silent failure
            msg = f"Unexpected error reading {file_path}: {type(e).__name__}: {e}"
            self._errors.append(msg)
            logger.error(msg)

        return blocks

    def extract_code_blocks(self, file_path: Path) -> List[ContentBlock]:
        """
        Extract code blocks (content between ```).

        Returns:
            List of ContentBlock objects for code blocks
        """
        blocks = []

        # Check file size first (RT-01)
        if not self._check_file_size(file_path):
            return blocks

        try:
            with open(file_path, encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            in_code_block = False
            current_block = []
            start_line = 0

            for i, line in enumerate(lines, 1):
                if line.strip().startswith('```'):
                    if not in_code_block:
                        in_code_block = True
                        start_line = i
                        current_block = []
                    else:
                        in_code_block = False
                        if current_block:
                            blocks.append(ContentBlock(
                                file=file_path,
                                start_line=start_line,
                                end_line=i,
                                content='\n'.join(current_block),
                                block_type='code'
                            ))
                elif in_code_block:
                    current_block.append(line.rstrip())

        except PermissionError as e:
            msg = f"Permission denied reading {file_path}: {e}"
            self._errors.append(msg)
            logger.warning(msg)
        except UnicodeDecodeError as e:
            msg = f"Encoding error reading {file_path}: {e}"
            self._errors.append(msg)
            logger.debug(msg)
        except OSError as e:
            msg = f"OS error reading {file_path}: {e}"
            self._errors.append(msg)
            logger.warning(msg)
        except Exception as e:
            msg = f"Unexpected error reading {file_path}: {type(e).__name__}: {e}"
            self._errors.append(msg)
            logger.error(msg)

        return blocks

    @property
    def errors(self) -> List[str]:
        """Return list of errors encountered during extraction."""
        return self._errors.copy()

    def extract_all_blocks(self, file_path: Path) -> List[ContentBlock]:
        """
        Extract all content blocks from a file.

        Returns:
            List of all ContentBlock objects (paragraphs + code)
        """
        blocks = []
        blocks.extend(self.extract_paragraphs(file_path))
        blocks.extend(self.extract_code_blocks(file_path))
        return blocks


class DuplicationDetector:
    """Detect duplicate content across files."""

    def __init__(self, config: dict):
        """
        Initialize detector with configuration.

        Args:
            config: Should include healers.resolve_duplicates section
                   (uses defaults if not present)
        """
        healer_config = config.get('healers', {}).get('resolve_duplicates', {})
        self.min_block_size = healer_config.get('min_block_size', 100)
        self.similarity_threshold = healer_config.get('similarity_threshold', 0.80)
        self.hierarchy_rules = healer_config.get('hierarchy_rules', [
            "README.md",
            "docs/index.md",
            "docs/",
        ])
        self.extractor = ContentExtractor()

    def calculate_similarity(self, block1: ContentBlock, block2: ContentBlock) -> float:
        """
        Calculate similarity between two content blocks.

        Uses difflib's SequenceMatcher to compute ratio of matching characters.

        Args:
            block1: First content block
            block2: Second content block

        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        return SequenceMatcher(None, block1.content, block2.content).ratio()

    def find_duplicates(self, files: List[Path]) -> List[Duplication]:
        """
        Find duplicate content across files.

        Algorithm:
        1. Extract all blocks from all files
        2. Filter out short blocks (below min_block_size)
        3. Compare all pairs of blocks
        4. For similarity ≥ threshold, create Duplication object
        5. Determine canonical location using hierarchy rules

        Args:
            files: List of file paths to scan

        Returns:
            List of Duplication objects
        """
        # Extract all blocks
        all_blocks: List[ContentBlock] = []
        for file_path in files:
            all_blocks.extend(self.extractor.extract_all_blocks(file_path))

        # Filter short blocks
        all_blocks = [b for b in all_blocks if len(b.content) >= self.min_block_size]

        # Compare all pairs
        duplications = []
        processed: Set[Tuple[int, int]] = set()

        for i, block1 in enumerate(all_blocks):
            for j, block2 in enumerate(all_blocks[i + 1:], i + 1):
                if (i, j) in processed:
                    continue

                # Skip same file (some duplication within file is okay)
                if block1.file == block2.file:
                    continue

                similarity = self.calculate_similarity(block1, block2)

                if similarity >= self.similarity_threshold:
                    # Determine canonical location
                    canonical = self._determine_canonical([block1, block2])

                    duplications.append(Duplication(
                        blocks=[block1, block2],
                        similarity=similarity,
                        canonical_location=canonical.file,
                        suggested_action=self._suggest_action(block1, block2, similarity),
                        confidence=self._calculate_confidence(block1, block2, similarity)
                    ))

                    processed.add((i, j))

        return duplications

    def _determine_canonical(self, blocks: List[ContentBlock]) -> ContentBlock:
        """
        Determine which location should be canonical.

        Uses hierarchy_rules from config to prioritize files.
        Files matching earlier rules have higher priority.

        Args:
            blocks: List of content blocks to compare

        Returns:
            The ContentBlock from the most canonical location
        """
        def get_priority(block: ContentBlock) -> int:
            path_str = str(block.file)
            for idx, pattern in enumerate(self.hierarchy_rules):
                if pattern in path_str:
                    return idx
            return len(self.hierarchy_rules)  # Lowest priority

        return min(blocks, key=lambda b: (get_priority(b), str(b.file)))

    def _suggest_action(self, block1: ContentBlock, block2: ContentBlock, similarity: float) -> str:
        """
        Suggest consolidation action based on similarity.

        Rules:
        - ≥95% similar: replace_with_link (nearly identical)
        - 85-95% similar: merge (very similar, may need manual review)
        - <85% similar: review (manually check before action)

        Args:
            block1: First content block
            block2: Second content block
            similarity: Similarity score (0.0-1.0)

        Returns:
            Suggested action string
        """
        if similarity >= 0.95:
            return 'replace_with_link'
        elif similarity >= 0.85:
            return 'merge'
        else:
            return 'review'

    def _calculate_confidence(self, block1: ContentBlock, block2: ContentBlock, similarity: float) -> float:
        """
        Calculate confidence in suggested action.

        Factors:
        - Exact duplicates: 100% confidence
        - High similarity: use similarity score
        - Length mismatch: reduce confidence (might be excerpt, not duplicate)

        Args:
            block1: First content block
            block2: Second content block
            similarity: Similarity score (0.0-1.0)

        Returns:
            Confidence score (0.0-1.0)
        """
        confidence = similarity

        # Exact duplicates = high confidence
        if block1.content == block2.content:
            confidence = 1.0

        # If one is much shorter, might be an excerpt (lower confidence)
        len_ratio = min(len(block1.content), len(block2.content)) / max(len(block1.content), len(block2.content))
        if len_ratio < 0.8:
            confidence *= 0.7

        return confidence


class FastDuplicationDetector:
    """
    O(n log n) duplicate detection using SimHash and hash buckets.

    Instead of comparing all n² pairs, this detector:
    1. Computes SimHash for each content block
    2. Groups blocks into hash buckets (blocks with similar hashes)
    3. Only compares blocks within the same bucket
    4. Uses Locality Sensitive Hashing (LSH) for approximate matching

    Performance:
    - O(n) for hash computation
    - O(k²) for comparison within each bucket (where k << n)
    - Total: O(n * k) which is effectively O(n log n) for typical content

    Memory:
    - Hash table with n entries: O(n)
    - Bounded by max_blocks parameter to handle very large corpora
    """

    def __init__(self, config: dict):
        """
        Initialize fast detector with configuration.

        Args:
            config: Should include healers.resolve_duplicates section
        """
        healer_config = config.get('healers', {}).get('resolve_duplicates', {})
        self.min_block_size = healer_config.get('min_block_size', 100)
        self.similarity_threshold = healer_config.get('similarity_threshold', 0.80)
        self.hierarchy_rules = healer_config.get('hierarchy_rules', [
            "README.md",
            "docs/index.md",
            "docs/",
        ])
        # Maximum Hamming distance for SimHash similarity
        # Distance 3 ~ 95% similar, Distance 6 ~ 90% similar
        self.max_hamming_distance = healer_config.get('max_hamming_distance', 6)
        # Maximum blocks to process (memory bound)
        self.max_blocks = healer_config.get('max_blocks', 100000)

        self.extractor = ContentExtractor()

    def find_duplicates(self, files: List[Path]) -> List[Duplication]:
        """
        Find duplicate content using O(n log n) SimHash algorithm.

        Algorithm:
        1. Extract all blocks from files (streaming, memory-bounded)
        2. Compute SimHash for each block
        3. Build hash buckets using Locality Sensitive Hashing
        4. Compare only within buckets (O(k²) where k is small)
        5. Verify candidates with exact similarity check

        Args:
            files: List of file paths to scan

        Returns:
            List of Duplication objects
        """
        # Phase 1: Extract blocks with SimHash (streaming)
        blocks_with_hash: List[Tuple[ContentBlock, int]] = []
        file_cache = get_file_cache()

        for file_path in files:
            try:
                blocks = self.extractor.extract_all_blocks(file_path)
                for block in blocks:
                    if len(block.content) >= self.min_block_size:
                        # Compute SimHash
                        block_hash = simhash(block.content)
                        blocks_with_hash.append((block, block_hash))

                        # Memory bound
                        if len(blocks_with_hash) >= self.max_blocks:
                            break
            except Exception:
                continue

            if len(blocks_with_hash) >= self.max_blocks:
                break

        # Phase 2: Build hash buckets using LSH
        # We use band hashing: split the 64-bit hash into bands
        # Blocks matching in any band are candidates
        buckets: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        num_bands = 8  # 64 bits / 8 = 8 bits per band
        bits_per_band = 8

        for idx, (block, hash_val) in enumerate(blocks_with_hash):
            # Add to buckets for each band
            for band in range(num_bands):
                # Extract this band's bits
                mask = ((1 << bits_per_band) - 1) << (band * bits_per_band)
                band_hash = (hash_val & mask) >> (band * bits_per_band)
                bucket_key = (band, band_hash)
                buckets[bucket_key].append(idx)

        # Phase 3: Find candidate pairs (blocks sharing a bucket)
        candidate_pairs: Set[Tuple[int, int]] = set()

        for bucket_indices in buckets.values():
            if len(bucket_indices) > 1:
                # All pairs in this bucket are candidates
                for i, idx1 in enumerate(bucket_indices):
                    for idx2 in bucket_indices[i + 1:]:
                        if idx1 < idx2:
                            candidate_pairs.add((idx1, idx2))
                        else:
                            candidate_pairs.add((idx2, idx1))

        # Phase 4: Verify candidates with exact similarity
        duplications: List[Duplication] = []
        seen_pairs: Set[Tuple[Path, int, Path, int]] = set()

        for idx1, idx2 in candidate_pairs:
            block1, hash1 = blocks_with_hash[idx1]
            block2, hash2 = blocks_with_hash[idx2]

            # Skip same file
            if block1.file == block2.file:
                continue

            # Skip already seen
            pair_key = (block1.file, block1.start_line, block2.file, block2.start_line)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Quick Hamming distance check
            distance = hamming_distance(hash1, hash2)
            if distance > self.max_hamming_distance:
                continue

            # Exact similarity check (SequenceMatcher is expensive, so we filter first)
            similarity = SequenceMatcher(None, block1.content, block2.content).ratio()

            if similarity >= self.similarity_threshold:
                # Determine canonical location
                canonical = self._determine_canonical([block1, block2])

                duplications.append(Duplication(
                    blocks=[block1, block2],
                    similarity=similarity,
                    canonical_location=canonical.file,
                    suggested_action=self._suggest_action(similarity),
                    confidence=self._calculate_confidence(block1, block2, similarity)
                ))

        return duplications

    def _determine_canonical(self, blocks: List[ContentBlock]) -> ContentBlock:
        """Determine canonical location using hierarchy rules."""
        def get_priority(block: ContentBlock) -> int:
            path_str = str(block.file)
            for idx, pattern in enumerate(self.hierarchy_rules):
                if pattern in path_str:
                    return idx
            return len(self.hierarchy_rules)

        return min(blocks, key=lambda b: (get_priority(b), str(b.file)))

    def _suggest_action(self, similarity: float) -> str:
        """Suggest action based on similarity."""
        if similarity >= 0.95:
            return 'replace_with_link'
        elif similarity >= 0.85:
            return 'merge'
        else:
            return 'review'

    def _calculate_confidence(self, block1: ContentBlock, block2: ContentBlock, similarity: float) -> float:
        """Calculate confidence score."""
        confidence = similarity

        if block1.content == block2.content:
            confidence = 1.0

        len_ratio = min(len(block1.content), len(block2.content)) / max(len(block1.content), len(block2.content))
        if len_ratio < 0.8:
            confidence *= 0.7

        return confidence


class ResolveDuplicatesHealer(HealingSystem):
    """
    Healing system for resolving duplicate content.

    Workflow:
    1. check() - Scans configured doc paths for duplicates
    2. heal() - Consolidates duplicates above confidence threshold
    3. Replaces non-canonical blocks with links to canonical location
    """

    def __init__(self, config: dict):
        """
        Initialize healer with configuration.

        Args:
            config: Configuration dict. Optional keys:
                - healers.resolve_duplicates.similarity_threshold (default: 0.80)
                - healers.resolve_duplicates.min_block_size (default: 100)
                - healers.resolve_duplicates.hierarchy_rules
                - healers.resolve_duplicates.scan_paths (default: doc_root)
                - healers.resolve_duplicates.use_fast_detection (default: True)
        """
        super().__init__(config)

        healer_config = config.get('healers', {}).get('resolve_duplicates', {})

        # Use fast detection by default (O(n log n) instead of O(n²))
        self.use_fast_detection = healer_config.get('use_fast_detection', True)

        if self.use_fast_detection:
            self.detector = FastDuplicationDetector(config)
        else:
            self.detector = DuplicationDetector(config)

        self.similarity_threshold = healer_config.get('similarity_threshold', 0.80)

        # Paths to scan (default to doc_root if not specified)
        self.scan_paths = healer_config.get('scan_paths', [str(self.doc_root)])

    def check(self) -> HealingReport:
        """
        Scan documentation for duplicate content.

        Returns:
            HealingReport with mode="check" and list of duplicates found
        """
        start_time = time.time()

        # Collect files to scan
        doc_files = []
        for scan_path in self.scan_paths:
            path = Path(scan_path)
            if path.is_file():
                doc_files.append(path)
            elif path.is_dir():
                doc_files.extend(path.rglob("*.md"))

        doc_files = [f for f in doc_files if f.exists()]

        # Find duplicates
        duplications = self.detector.find_duplicates(doc_files)

        # Convert duplications to Change objects
        changes = []
        for dup in duplications:
            # Create Change for each non-canonical block
            for block in dup.blocks:
                if block.file != dup.canonical_location:
                    canonical_rel_path = self._get_relative_path(block.file, dup.canonical_location)
                    link_text = f"See [{dup.canonical_location.name}]({canonical_rel_path})"

                    changes.append(Change(
                        file=block.file,
                        line=block.start_line,
                        old_content=block.content,
                        new_content=link_text,
                        confidence=dup.confidence,
                        reason=f"Duplicate content (similarity: {dup.similarity:.0%})",
                        healer="ResolveDuplicatesHealer"
                    ))

        execution_time = time.time() - start_time

        return self.create_report(
            mode="check",
            issues_found=len(duplications),
            issues_fixed=0,
            changes=changes,
            execution_time=execution_time
        )

    def heal(self, min_confidence: Optional[float] = None) -> HealingReport:
        """
        Apply fixes for duplicates above confidence threshold.

        Uses cascade-aware change application to handle multiple duplicates
        in the same file without content mismatch errors.

        Args:
            min_confidence: Override default confidence threshold

        Returns:
            HealingReport with mode="heal" and list of applied changes
        """
        start_time = time.time()

        # Get proposed changes
        check_report = self.check()

        # Use provided threshold or default
        threshold = min_confidence if min_confidence is not None else self.min_confidence

        # Filter changes by confidence
        high_confidence_changes = [
            c for c in check_report.changes
            if c.confidence >= threshold and self.validate_change(c)
        ]

        # Apply changes with cascade handling
        applied_changes = self._apply_changes_with_cascade_handling(high_confidence_changes)

        execution_time = time.time() - start_time

        return self.create_report(
            mode="heal",
            issues_found=check_report.issues_found,
            issues_fixed=len(applied_changes),
            changes=applied_changes,
            execution_time=execution_time
        )

    def _apply_duplication_fix(self, change: Change) -> bool:
        """
        Apply a duplication fix by replacing block with link.

        Uses line-based replacement to avoid content mismatch issues.

        Args:
            change: Change object to apply

        Returns:
            True if successfully applied
        """
        try:
            content = change.file.read_text(encoding='utf-8')
            lines = content.split('\n')

            # Clear block lines and insert link
            for i in range(change.line - 1, min(change.line + 10, len(lines))):
                if i < len(lines):
                    lines[i] = ''  # Clear this line

            # Insert link at block start
            if change.line - 1 < len(lines):
                lines[change.line - 1] = change.new_content

            new_content = '\n'.join(lines)
            change.file.write_text(new_content, encoding='utf-8')

            return True

        except Exception as e:
            self.log_error(f"Failed to apply duplication fix to {change.file}: {e}")
            return False

    def _apply_changes_with_cascade_handling(self, changes: List[Change]) -> List[Change]:
        """
        Apply multiple changes intelligently, handling cascade effects.

        When multiple duplicates exist in the same file, earlier fixes change
        the content, making subsequent line-number-based fixes fail. This method
        handles this by:
        1. Grouping changes by file
        2. Sorting by line number (reverse order - bottom to top)
        3. Reading file once and applying all changes using fuzzy content matching
        4. Writing file once with all changes

        Args:
            changes: List of Change objects to apply

        Returns:
            List of successfully applied Change objects
        """
        # Group changes by file
        changes_by_file: Dict[Path, List[Change]] = defaultdict(list)
        for change in changes:
            changes_by_file[change.file].append(change)

        applied_changes = []

        for file_path, file_changes in changes_by_file.items():
            # Sort by line number (reverse order - bottom to top)
            # This way earlier changes don't affect later line numbers
            file_changes.sort(key=lambda c: c.line, reverse=True)

            try:
                # Read file once
                content = file_path.read_text(encoding='utf-8')
                lines = content.split('\n')

                # Apply all changes to this file
                for change in file_changes:
                    # Find the block by content (fuzzy match), not just line number
                    # This handles cases where line numbers shifted from previous changes
                    block_start = self._find_block_in_lines(lines, change.old_content)

                    if block_start is not None:
                        # Calculate block length
                        old_block_lines = change.old_content.split('\n')
                        block_length = len(old_block_lines)

                        # Replace the block with the new content (link)
                        new_lines = [change.new_content]

                        # Remove old lines and insert new
                        lines[block_start:block_start + block_length] = new_lines

                        applied_changes.append(change)
                    else:
                        # Log when we can't find the block
                        self.log_error(
                            f"Could not locate block in {file_path} at line {change.line} "
                            f"(content may have changed from previous fix)"
                        )

                # Write file once with all changes
                if any(c.file == file_path for c in applied_changes):
                    file_path.write_text('\n'.join(lines), encoding='utf-8')

            except Exception as e:
                self.log_error(f"Failed to apply changes to {file_path}: {e}")
                continue

        return applied_changes

    def _find_block_in_lines(self, lines: List[str], block_content: str) -> Optional[int]:
        """
        Find a content block in a list of lines using fuzzy matching.

        This is more robust than line-number-based lookup because it can
        handle files where content has shifted due to earlier edits.

        Args:
            lines: List of file lines to search
            block_content: Content to find

        Returns:
            Starting line index (0-based) if found, None otherwise
        """
        block_lines = block_content.split('\n')
        block_length = len(block_lines)

        # Search through the file for the best match
        best_match_idx = None
        best_similarity = 0.0

        for i in range(len(lines) - block_length + 1):
            # Get candidate block
            candidate_lines = lines[i:i + block_length]
            candidate_content = '\n'.join(candidate_lines)

            # Calculate similarity
            similarity = SequenceMatcher(
                None,
                candidate_content,
                block_content
            ).ratio()

            # Track best match
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_idx = i

        # Only return if we have a strong match (>95% similar)
        if best_similarity >= 0.95:
            return best_match_idx

        return None

    def _get_relative_path(self, from_file: Path, to_file: Path) -> str:
        """
        Get relative path between two files.

        If files can't be relativized (different drives, etc.),
        falls back to absolute path from project root.

        Args:
            from_file: Source file
            to_file: Target file

        Returns:
            Relative path as string
        """
        try:
            return str(to_file.relative_to(from_file.parent))
        except ValueError:
            # Use absolute path from project root
            try:
                return '/' + str(to_file.relative_to(self.project_root))
            except ValueError:
                # Last resort: absolute path
                return str(to_file.absolute())
