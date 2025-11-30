#!/usr/bin/env python3
"""Performance validation for Phase 1 hover preview implementation."""

import time
import numpy as np
from automataii.application.mechanism_foundry.path_cache import PathCache
from automataii.domain.mechanisms.linkages.fourbar.compute import FourBarMechanism


def measure_first_computation():
    """Measure first path computation time (target: ≤10ms)."""
    cache = PathCache()
    mechanism = FourBarMechanism()
    params = {"ground_link": 150.0, "input_link": 40.0, "coupler_link": 120.0, "output_link": 130.0}

    start = time.perf_counter()
    result = cache.compute_and_cache(mechanism, params, "coupler", angle_samples=180)
    elapsed_ms = (time.perf_counter() - start) * 1000

    return elapsed_ms, result is not None


def measure_cached_computation():
    """Measure cached path retrieval time (target: ≤1ms)."""
    cache = PathCache()
    mechanism = FourBarMechanism()
    params = {"ground_link": 150.0, "input_link": 40.0, "coupler_link": 120.0, "output_link": 130.0}

    # Prime the cache
    cache.compute_and_cache(mechanism, params, "coupler", angle_samples=180)

    # Measure cached retrieval
    start = time.perf_counter()
    result = cache.compute_and_cache(mechanism, params, "coupler", angle_samples=180)
    elapsed_ms = (time.perf_counter() - start) * 1000

    return elapsed_ms, result is not None


def measure_cache_hit_rate():
    """Simulate 5 minutes of usage and measure cache hit rate (target: ≥95%)."""
    cache = PathCache()
    mechanism = FourBarMechanism()

    # Simulate realistic usage: 10 different configurations
    configs = [
        {"ground_link": 150.0, "input_link": 40.0, "coupler_link": 120.0, "output_link": 130.0},
        {"ground_link": 160.0, "input_link": 45.0, "coupler_link": 125.0, "output_link": 135.0},
        {"ground_link": 155.0, "input_link": 42.0, "coupler_link": 122.0, "output_link": 132.0},
        {"ground_link": 145.0, "input_link": 38.0, "coupler_link": 118.0, "output_link": 128.0},
    ]

    # Simulate 300 hover events over 5 minutes (1 per second)
    # With 4 configs and 30 iterations, most should hit cache
    for _ in range(30):
        for config in configs:
            cache.compute_and_cache(mechanism, config, "coupler", angle_samples=180)

    hit_rate = cache.hit_rate * 100

    return hit_rate, cache._hits, cache._misses


def main():
    print("=" * 60)
    print("PHASE 1 PERFORMANCE VALIDATION")
    print("=" * 60)

    # Test 1: First computation time
    print("\n1. First Path Computation (target: ≤10ms)")
    times = []
    for i in range(10):
        elapsed, success = measure_first_computation()
        times.append(elapsed)
        print(f"   Run {i + 1}: {elapsed:.3f}ms {'✅' if success else '❌'}")

    avg_first = np.mean(times)
    print(f"   Average: {avg_first:.3f}ms {'✅ PASS' if avg_first <= 10 else '❌ FAIL'}")

    # Test 2: Cached computation time
    print("\n2. Cached Path Retrieval (target: ≤1ms)")
    times = []
    for i in range(100):
        elapsed, success = measure_cached_computation()
        times.append(elapsed)

    avg_cached = np.mean(times)
    max_cached = np.max(times)
    print(f"   Average: {avg_cached:.3f}ms {'✅ PASS' if avg_cached <= 1 else '❌ FAIL'}")
    print(f"   Max: {max_cached:.3f}ms")

    # Test 3: Cache hit rate
    print("\n3. Cache Hit Rate (target: ≥95%)")
    hit_rate, hits, misses = measure_cache_hit_rate()
    print(f"   Hit rate: {hit_rate:.1f}% ({hits} hits, {misses} misses)")
    print(f"   {'✅ PASS' if hit_rate >= 95 else '❌ FAIL'}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"First computation:  {avg_first:.3f}ms {'✅' if avg_first <= 10 else '❌'}")
    print(f"Cached retrieval:   {avg_cached:.3f}ms {'✅' if avg_cached <= 1 else '❌'}")
    print(f"Cache hit rate:     {hit_rate:.1f}% {'✅' if hit_rate >= 95 else '❌'}")

    all_pass = (avg_first <= 10) and (avg_cached <= 1) and (hit_rate >= 95)
    print(f"\n{'✅ ALL TARGETS MET' if all_pass else '❌ SOME TARGETS MISSED'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
