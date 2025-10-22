import glob
import statistics
import re
import numpy as np
import matplotlib.pyplot as plt

def parse_latency_file(filename):
    """Parse latency data from a text file."""
    latencies = []
    timestamps = []
    pattern = re.compile(r"latency=([\d\.eE+-]+).*timestamp=([\d\.eE+-]+)")

    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                lat = float(match.group(1)) / 1000.0 # give it in ms
                ts = float(match.group(2))
                # adjust to milliseconds
                latencies.append(lat)
                timestamps.append(ts)
    return latencies, timestamps


def detect_outliers(latencies):
    """Detect outliers using the IQR rule."""
    q1 = np.percentile(latencies, 25)
    q3 = np.percentile(latencies, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    outliers = [x for x in latencies if x < lower_bound or x > upper_bound]
    return outliers, lower_bound, upper_bound


def analyze_file(filename):
    """Compute statistics and detect outliers for a single file."""

    latencies, timestamps = parse_latency_file(filename)

    if not latencies:
        print(f"[WARN] No valid data found in {filename}")
        return

    avg = statistics.mean(latencies)
    stdev = statistics.stdev(latencies) if len(latencies) > 1 else 0
    min_lat = min(latencies)
    max_lat = max(latencies)

    outliers, low, high = detect_outliers(latencies)

    lines = []
    lines.append(f"\n📄 File: {filename}")
    lines.append(f"  Samples: {len(latencies)}")
    lines.append(f"  Avg time: {avg:.3f} ms")
    lines.append(f"  Min time: {min_lat:.3f} ms")
    lines.append(f"  Max time: {max_lat:.3f} ms")
    lines.append(f"  Std Dev: {stdev:.3f} ms")
    lines.append(f"  Outliers: {len(outliers)} (outside {low:.3f}–{high:.3f} ms)")
    if outliers:
        lines.append(f"    → Example outliers (first 3): {[f'{x:.3f} ms' for x in outliers[:3]]}")

    with open("results.log", "a", encoding="utf-8") as file:
        for line in lines:
            file.write(f"{line}\n")
            print(line)

    # Optional plot
    plt.figure(figsize=(8,4))
    plt.plot(timestamps, latencies, '.', label='Latency (ms)', alpha=0.7)
    plt.title(f"Execution over Time: {filename}")
    plt.xlabel("Timestamp (s)")
    plt.ylabel("Execution Time (ms)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{filename}.png", dpi=300, bbox_inches='tight')
    #plt.show()

def main():
    # Change this pattern if needed (e.g., data/*.txt)
    for filename in glob.glob("*.log"):
        analyze_file(filename)


if __name__ == "__main__":
    main()
