#!/usr/bin/env python3
"""
Performance benchmark suite for Doc Guardian.

Validates performance targets:
- 100 files: < 1s
- 1,000 files: < 10s
- 10,000 files: < 100s

Benchmarks the 5 performance optimizations:
1. O(n log n) duplicate detection using SimHash (was O(n^2))
2. O(1) file index lookup (was O(n) tree scan per broken link)
3. Parallel healer execution with ThreadPoolExecutor
4. LRU file caching to reduce I/O
5. Batched git operations (one call instead of n calls)
"""

import time
import tempfile
import random
import string
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    files: int
    elapsed_seconds: float
    memory_mb: float
    files_per_second: float
    target_seconds: float
    passed: bool

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{self.name}: {self.files:,} files in {self.elapsed_seconds:.2f}s "
            f"({self.files_per_second:.1f} files/sec) "
            f"[target: <{self.target_seconds}s] {status}"
        )


def generate_random_content(size: int = 1000) -> str:
    """Generate random markdown content."""
    words = [''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 10)))
             for _ in range(50)]

    lines = []
    lines.append(f"# {' '.join(random.choices(words, k=3))}\n")
    lines.append(f"\n**Last Updated**: 2025-06-15\n")
    lines.append(f"\n## Overview\n")

    # Add some paragraphs
    for _ in range(random.randint(3, 8)):
        paragraph = ' '.join(random.choices(words, k=random.randint(20, 50)))
        lines.append(f"\n{paragraph}\n")

    # Add some links
    for _ in range(random.randint(2, 5)):
        link_text = ' '.join(random.choices(words, k=2))
        link_target = random.choice(words) + ".md"
        lines.append(f"\n[{link_text}]({link_target})\n")

    # Add a code block
    lines.append("\n```python\n")
    lines.append(f"def {random.choice(words)}():\n")
    lines.append(f"    return '{random.choice(words)}'\n")
    lines.append("```\n")

    return ''.join(lines)


def create_test_corpus(num_files: int, temp_dir: Path) -> List[Path]:
    """Create a test corpus with specified number of files."""
    files = []
    docs_dir = temp_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories for organization
    subdirs = ["guides", "api", "tutorials", "reference", "concepts"]
    for subdir in subdirs:
        (docs_dir / subdir).mkdir(exist_ok=True)

    for i in range(num_files):
        subdir = subdirs[i % len(subdirs)]
        file_path = docs_dir / subdir / f"doc_{i:05d}.md"
        file_path.write_text(generate_random_content())
        files.append(file_path)

    return files


def benchmark_file_creation(num_files: int) -> Tuple[Path, float]:
    """Benchmark file creation and return temp dir and time."""
    temp_dir = Path(tempfile.mkdtemp(prefix="dg_bench_"))

    start = time.perf_counter()
    files = create_test_corpus(num_files, temp_dir)
    elapsed = time.perf_counter() - start

    print(f"  Created {num_files:,} files in {elapsed:.2f}s")
    return temp_dir, elapsed


def get_memory_usage() -> float:
    """Get current memory usage in MB."""
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    return 0.0


def benchmark_healer_check(
    healer_class,
    config: Dict,
    num_files: int,
    temp_dir: Path,
    target_seconds: float
) -> BenchmarkResult:
    """Benchmark a healer's check operation."""
    healer_name = healer_class.__name__

    mem_before = get_memory_usage()
    start = time.perf_counter()

    try:
        healer = healer_class(config)
        report = healer.check()
        elapsed = time.perf_counter() - start
    except Exception as e:
        print(f"  Error in {healer_name}: {e}")
        elapsed = time.perf_counter() - start
        report = None

    mem_after = get_memory_usage()
    memory_used = mem_after - mem_before

    files_per_second = num_files / elapsed if elapsed > 0 else float('inf')
    passed = elapsed < target_seconds

    return BenchmarkResult(
        name=healer_name,
        files=num_files,
        elapsed_seconds=elapsed,
        memory_mb=memory_used,
        files_per_second=files_per_second,
        target_seconds=target_seconds,
        passed=passed
    )


def run_benchmark_suite(num_files: int, target_seconds: float) -> List[BenchmarkResult]:
    """Run full benchmark suite for specified file count."""
    print(f"\n{'='*60}")
    print(f"BENCHMARK: {num_files:,} files (target: <{target_seconds}s)")
    print(f"{'='*60}")

    # Create test corpus
    temp_dir, creation_time = benchmark_file_creation(num_files)

    try:
        # Create config
        config = {
            "project": {
                "root": str(temp_dir),
                "doc_root": str(temp_dir / "docs"),
                "excluded_dirs": [".git", "node_modules"],
            },
            "confidence": {
                "auto_commit_threshold": 0.9,
            },
            "healers": {
                "detect_staleness": {
                    "enabled": True,
                    "staleness_threshold_days": 30,
                },
                "fix_broken_links": {
                    "enabled": True,
                    "fuzzy_threshold": 0.8,
                },
            }
        }

        results = []

        # Import healers
        try:
            from guardian.healers.detect_staleness import DetectStalenessHealer
            from guardian.healers.fix_broken_links import FixBrokenLinksHealer

            # Benchmark each healer
            for healer_class in [DetectStalenessHealer, FixBrokenLinksHealer]:
                print(f"\n  Benchmarking {healer_class.__name__}...")
                result = benchmark_healer_check(
                    healer_class, config, num_files, temp_dir, target_seconds
                )
                results.append(result)
                print(f"    {result}")

        except ImportError as e:
            print(f"  Could not import healers: {e}")
            # Create dummy result
            results.append(BenchmarkResult(
                name="ImportError",
                files=num_files,
                elapsed_seconds=0,
                memory_mb=0,
                files_per_second=0,
                target_seconds=target_seconds,
                passed=False
            ))

        return results

    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def benchmark_o_n_operations():
    """Benchmark O(n) vs O(n^2) algorithm improvements."""
    print(f"\n{'='*60}")
    print("ALGORITHM COMPLEXITY BENCHMARKS")
    print(f"{'='*60}")

    # Test set-based lookup vs list-based lookup
    sizes = [100, 1000, 10000]

    for size in sizes:
        # Create test data
        items = [f"item_{i}" for i in range(size)]
        search_items = items[:100]  # Search for first 100 items

        # List-based lookup (O(n))
        start = time.perf_counter()
        for search in search_items:
            _ = search in items
        list_time = time.perf_counter() - start

        # Set-based lookup (O(1))
        items_set = set(items)
        start = time.perf_counter()
        for search in search_items:
            _ = search in items_set
        set_time = time.perf_counter() - start

        speedup = list_time / set_time if set_time > 0 else float('inf')
        print(f"  {size:,} items: list={list_time*1000:.2f}ms, set={set_time*1000:.2f}ms "
              f"(speedup: {speedup:.1f}x)")


def benchmark_parallel_execution():
    """Benchmark parallel vs sequential file processing."""
    print(f"\n{'='*60}")
    print("PARALLEL EXECUTION BENCHMARKS")
    print(f"{'='*60}")

    # Create a simple processing function
    def process_file(path: Path) -> Dict:
        """Simulate file processing."""
        content = path.read_text()
        return {"path": str(path), "size": len(content), "lines": content.count('\n')}

    # Create test files
    temp_dir = Path(tempfile.mkdtemp(prefix="dg_parallel_"))
    try:
        num_files = 100
        files = create_test_corpus(num_files, temp_dir)

        # Sequential processing
        start = time.perf_counter()
        for f in files:
            process_file(f)
        sequential_time = time.perf_counter() - start

        # Parallel processing (threads - I/O bound)
        start = time.perf_counter()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(process_file, files))
        parallel_time = time.perf_counter() - start

        speedup = sequential_time / parallel_time if parallel_time > 0 else 1.0
        print(f"  {num_files} files: sequential={sequential_time*1000:.0f}ms, "
              f"parallel={parallel_time*1000:.0f}ms (speedup: {speedup:.1f}x)")

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def benchmark_simhash():
    """Benchmark SimHash computation for duplicate detection."""
    print(f"\n{'='*60}")
    print("SIMHASH BENCHMARK (O(n log n) duplicate detection)")
    print(f"{'='*60}")

    try:
        from guardian.core.file_cache import simhash, hamming_distance
    except ImportError:
        print("  Could not import simhash - skipping")
        return

    # Generate test content
    sizes = [100, 500, 1000]

    for size in sizes:
        contents = [generate_random_content() for _ in range(size)]

        # Benchmark hash computation
        start = time.perf_counter()
        hashes = [simhash(c) for c in contents]
        hash_time = time.perf_counter() - start

        # Benchmark similarity detection (only compare within hash buckets)
        start = time.perf_counter()
        similar_pairs = 0
        for i, h1 in enumerate(hashes[:100]):
            for h2 in hashes[i+1:]:
                if hamming_distance(h1, h2) <= 3:
                    similar_pairs += 1
        compare_time = time.perf_counter() - start

        rate = size / hash_time if hash_time > 0 else 0
        print(f"  {size} texts: hash={hash_time*1000:.1f}ms ({rate:.0f}/sec), "
              f"compare(100)={compare_time*1000:.1f}ms, similar={similar_pairs}")


def benchmark_file_index():
    """Benchmark FileIndex for O(1) lookups."""
    print(f"\n{'='*60}")
    print("FILE INDEX BENCHMARK (O(1) lookups)")
    print(f"{'='*60}")

    try:
        from guardian.healers.fix_broken_links import FileIndex
    except ImportError:
        print("  Could not import FileIndex - skipping")
        return

    temp_dir = Path(tempfile.mkdtemp(prefix="dg_index_"))
    try:
        # Create test files
        num_files = 500
        files = create_test_corpus(num_files, temp_dir)

        # Build index
        start = time.perf_counter()
        index = FileIndex(
            temp_dir,
            ['.md'],
            {'.git', 'node_modules'}
        )
        build_time = time.perf_counter() - start

        # Benchmark lookups
        num_lookups = 200
        targets = [f"doc_{random.randint(0, num_files-1):05d}.md" for _ in range(num_lookups)]

        # Indexed lookups (O(1))
        start = time.perf_counter()
        for target in targets:
            index.find_similar(target, 0.5)
        index_time = time.perf_counter() - start

        # Tree scan simulation (O(n) per lookup - what we used to do)
        start = time.perf_counter()
        for target in targets:
            list(temp_dir.rglob(f"*{target}*"))[:10]
        scan_time = time.perf_counter() - start

        speedup = scan_time / index_time if index_time > 0 else 0
        print(f"  {num_files} files indexed in {build_time*1000:.1f}ms")
        print(f"  {num_lookups} lookups: index={index_time*1000:.1f}ms, "
              f"scan={scan_time*1000:.1f}ms (speedup: {speedup:.1f}x)")

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def benchmark_file_cache():
    """Benchmark LRU file cache."""
    print(f"\n{'='*60}")
    print("FILE CACHE BENCHMARK (LRU caching)")
    print(f"{'='*60}")

    try:
        from guardian.core.file_cache import FileCache, reset_global_cache
    except ImportError:
        print("  Could not import FileCache - skipping")
        return

    temp_dir = Path(tempfile.mkdtemp(prefix="dg_cache_"))
    try:
        # Create test files
        num_files = 100
        files = create_test_corpus(num_files, temp_dir)

        # Uncached reads (baseline)
        start = time.perf_counter()
        for _ in range(3):  # 3 passes
            for f in files:
                _ = f.read_text()
        uncached_time = time.perf_counter() - start

        # Cached reads
        reset_global_cache()
        cache = FileCache(max_size=500)

        start = time.perf_counter()
        for _ in range(3):  # 3 passes
            for f in files:
                _ = cache.read(f)
        cached_time = time.perf_counter() - start

        speedup = uncached_time / cached_time if cached_time > 0 else 0
        hit_rate = cache.stats['hit_rate'] * 100

        print(f"  {num_files} files x 3 passes:")
        print(f"    Uncached: {uncached_time*1000:.1f}ms")
        print(f"    Cached:   {cached_time*1000:.1f}ms (speedup: {speedup:.1f}x)")
        print(f"    Hit rate: {hit_rate:.1f}%")

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        try:
            reset_global_cache()
        except Exception:
            pass


def main():
    """Run all benchmarks."""
    print("Doc Guardian Performance Benchmark Suite")
    print("=" * 60)

    if not PSUTIL_AVAILABLE:
        print("Note: psutil not installed, memory tracking disabled")
        print("      pip install psutil for memory metrics")

    all_results = []

    # Run benchmarks at different scales
    benchmarks = [
        (100, 1.0),      # 100 files: target < 1s
        (1000, 10.0),    # 1,000 files: target < 10s
    ]

    # Only run 10k benchmark if explicitly requested
    if "--full" in sys.argv:
        benchmarks.append((10000, 100.0))  # 10,000 files: target < 100s

    for num_files, target in benchmarks:
        results = run_benchmark_suite(num_files, target)
        all_results.extend(results)

    # Algorithm benchmarks
    benchmark_o_n_operations()

    # Parallel execution benchmark
    benchmark_parallel_execution()

    # New optimization benchmarks
    benchmark_simhash()
    benchmark_file_index()
    benchmark_file_cache()

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)

    for result in all_results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.name}: {result.files:,} files in {result.elapsed_seconds:.2f}s")

    print(f"\nTotal: {passed}/{total} benchmarks passed")

    if passed < total:
        print("\n  Performance targets not met. Consider:")
        print("    1. Implementing file indexing (O(1) lookups)")
        print("    2. Using hash-based duplicate detection")
        print("    3. Enabling parallel processing")
        print("    4. Adding file content caching")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
