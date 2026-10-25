"""C11 yourself: measure the pipeline's real speed, median and p95.

Needs the Ollama app open. About 20 seconds.  Run:  python diy/c11_timing.py
"""

import time

from mini_pipeline import DEV, answer

# 1. Warm up: the first requests wake the model up and are slower, so they are not counted.
for r in DEV[:3]:
    answer(r["utt"])

# 2. Time 30 requests with a stopwatch.
times = []
for r in DEV[3:33]:
    start = time.perf_counter()
    answer(r["utt"])
    times.append(time.perf_counter() - start)

# 3. Sort them. The median is the middle one; p95 is the one 95% of requests are faster than.
times.sort()
print("sorted times (s):", [round(t, 2) for t in times])
print(f"median: {times[len(times) // 2]:.2f} s")
print(f"p95:    {times[min(len(times) - 1, int(0.95 * len(times)))]:.2f} s")
