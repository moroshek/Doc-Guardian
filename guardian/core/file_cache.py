"""
File Cache Module - LRU caching for file content reads.

Provides efficient caching to avoid repeated file reads across healers.
Reduces I/O overhead by caching file content with TTL and LRU eviction.

Performance impact:
- Files read 3-7x by different healers → 1x with cache
- Memory bounded by max_size parameter
- TTL ensures freshness for long-running operations
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
import time
import hashlib


@dataclass
class CacheEntry:
    """A cached file entry with metadata."""
    content: str
    mtime: float  # File modification time when cached
    cached_at: float  # When this entry was cached
    size: int  # Content size in bytes


class FileCache:
    """
    LRU cache for file content with TTL support.

    Features:
    - LRU eviction when max_size is reached
    - TTL-based expiration for freshness
    - mtime tracking to detect file changes
    - Memory-bounded by max_size

    Usage:
        cache = FileCache(max_size=1000, ttl_seconds=300)
        content = cache.read(Path("/path/to/file.md"))
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0):
        """
        Initialize file cache.

        Args:
            max_size: Maximum number of files to cache (default: 1000)
            ttl_seconds: Time-to-live for cache entries in seconds (default: 5 minutes)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[Path, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def read(self, file_path: Path) -> str:
        """
        Read file content, using cache if available.

        Args:
            file_path: Path to file to read

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file does not exist
            IOError: If file cannot be read
        """
        file_path = file_path.resolve()

        # Check cache
        entry = self._cache.get(file_path)

        if entry is not None:
            # Validate cache entry
            current_time = time.time()

            # Check TTL
            if current_time - entry.cached_at > self.ttl_seconds:
                # Expired - remove and re-read
                del self._cache[file_path]
            else:
                # Check if file was modified
                try:
                    current_mtime = file_path.stat().st_mtime
                    if current_mtime <= entry.mtime:
                        # Cache hit - move to end (most recently used)
                        self._cache.move_to_end(file_path)
                        self._hits += 1
                        return entry.content
                except OSError:
                    # File stat failed - remove from cache
                    del self._cache[file_path]

        # Cache miss - read file
        self._misses += 1
        content = file_path.read_text(encoding='utf-8')

        # Add to cache
        self._add_to_cache(file_path, content)

        return content

    def read_lines(self, file_path: Path) -> List[str]:
        """
        Read file and return lines.

        Args:
            file_path: Path to file

        Returns:
            List of lines (without newlines)
        """
        content = self.read(file_path)
        return content.split('\n')

    def _add_to_cache(self, file_path: Path, content: str):
        """Add content to cache with eviction if needed."""
        # Evict oldest entries if at capacity
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # Remove oldest (first) item

        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            mtime = time.time()

        self._cache[file_path] = CacheEntry(
            content=content,
            mtime=mtime,
            cached_at=time.time(),
            size=len(content)
        )

    def invalidate(self, file_path: Path):
        """
        Invalidate a cache entry.

        Call this after modifying a file to ensure fresh reads.

        Args:
            file_path: Path to invalidate
        """
        file_path = file_path.resolve()
        if file_path in self._cache:
            del self._cache[file_path]

    def clear(self):
        """Clear entire cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> Dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        total_size = sum(e.size for e in self._cache.values())

        return {
            'entries': len(self._cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': hit_rate,
            'total_cached_bytes': total_size
        }


# Global cache instance for sharing across healers
_global_cache: Optional[FileCache] = None


def get_file_cache(max_size: int = 1000, ttl_seconds: float = 300.0) -> FileCache:
    """
    Get global file cache instance.

    Creates a new cache if one doesn't exist.
    Reuses existing cache for sharing across healers.

    Args:
        max_size: Maximum cache size (only used if creating new cache)
        ttl_seconds: TTL for entries (only used if creating new cache)

    Returns:
        FileCache instance
    """
    global _global_cache

    if _global_cache is None:
        _global_cache = FileCache(max_size=max_size, ttl_seconds=ttl_seconds)

    return _global_cache


def reset_global_cache():
    """Reset the global cache (useful for testing)."""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
    _global_cache = None


# Content hash utilities for duplicate detection
def content_hash(text: str) -> str:
    """
    Compute MD5 hash of text content.

    Used for exact duplicate detection.

    Args:
        text: Text to hash

    Returns:
        Hex string of MD5 hash
    """
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def simhash(text: str, hash_bits: int = 64) -> int:
    """
    Compute SimHash for fuzzy duplicate detection.

    SimHash is a locality-sensitive hash that produces similar
    hashes for similar content. Two texts with Hamming distance
    < 3 in their SimHashes are likely duplicates.

    Algorithm:
    1. Tokenize text into words
    2. Hash each word to a 64-bit value
    3. For each bit position, sum +1 or -1 based on bit value
    4. Final hash: bit i = 1 if sum[i] >= 0, else 0

    Args:
        text: Text to hash
        hash_bits: Number of bits in hash (default: 64)

    Returns:
        Integer representing the SimHash
    """
    # Tokenize - split on whitespace and normalize
    tokens = text.lower().split()

    if not tokens:
        return 0

    # Initialize bit counters
    v = [0] * hash_bits

    # Process each token
    for token in tokens:
        # Hash token to bits
        h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)

        # Update bit counters
        for i in range(hash_bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    # Generate final fingerprint
    fingerprint = 0
    for i in range(hash_bits):
        if v[i] >= 0:
            fingerprint |= (1 << i)

    return fingerprint


def hamming_distance(hash1: int, hash2: int, bits: int = 64) -> int:
    """
    Compute Hamming distance between two hashes.

    Hamming distance = number of bits that differ.
    For SimHash, distance < 3 typically indicates similar content.

    Args:
        hash1: First hash
        hash2: Second hash
        bits: Number of bits to compare (default: 64)

    Returns:
        Number of differing bits
    """
    xor = hash1 ^ hash2
    distance = 0

    for i in range(bits):
        if xor & (1 << i):
            distance += 1

    return distance


def are_similar(hash1: int, hash2: int, max_distance: int = 3) -> bool:
    """
    Check if two SimHashes indicate similar content.

    Args:
        hash1: First SimHash
        hash2: Second SimHash
        max_distance: Maximum Hamming distance for similarity

    Returns:
        True if hashes are similar
    """
    return hamming_distance(hash1, hash2) <= max_distance
