import time
import statistics
import atexit
import sys


def get_benchmark_stats(times: list[float]):
    sorted_times = sorted(times)
    slen = len(sorted_times)

    def percentile(p: float):
        return sorted_times[int(slen * p)]

    stats = {
        "min": min(sorted_times),
        "25p": percentile(0.25),
        "50p": statistics.median(sorted_times),
        "75p": percentile(0.75),
        "90p": percentile(0.90),
        "95p": percentile(0.95),
        "max": max(sorted_times),
    }
    return stats


def format_time(seconds: float) -> str:
    """Convert seconds into a human-readable format."""
    if seconds < 1e-3:  # Less than 1 millisecond
        return f"{seconds * 1e6:.2f} µs"  # Microseconds
    elif seconds < 1:  # Less than 1 second
        return f"{seconds * 1e3:.2f} ms"  # Milliseconds
    elif seconds < 60:  # Less than 1 minute
        return f"{seconds:.2f} s"  # Seconds
    else:  # Greater than or equal to 1 minute
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.2f}s"  # Minutes and seconds


def is_pytest_running():
    return any("pytest" in arg for arg in sys.argv)


PYTEST_RUNNING = is_pytest_running()


def benchmark(func):
    if not PYTEST_RUNNING:
        return func

    times: list[float] = []

    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        total_time = end_time - start_time
        times.append(total_time)
        return result

    def exit_handler():
        stats = get_benchmark_stats(times)
        print(f"\nBenchmark stats for {func.__name__}")
        print("=" * 40)
        print(f"{'Metric':<15}{'Value':<15}")
        print("-" * 40)
        for key, value in stats.items():
            print(f"{key:<15}{format_time(value):<15}")
        print("=" * 40)

    atexit.register(exit_handler)

    return wrapper
