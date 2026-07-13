import threading
import time
from ttl_cache import TTLCache


def test_same_key_single_flight_under_contention():
    cache = TTLCache(ttl_seconds=10)
    calls = 0
    lock = threading.Lock()
    barrier = threading.Barrier(8)
    def factory():
        nonlocal calls
        with lock:
            calls += 1
        time.sleep(0.05)
        return "value"
    results = []
    def worker():
        barrier.wait()
        results.append(cache.get_or_compute("same", factory))
    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert results == ["value"] * 8
    assert calls == 1


def test_different_keys_are_not_serialized():
    cache = TTLCache(ttl_seconds=10)
    barrier = threading.Barrier(4)
    def worker(key):
        barrier.wait()
        return cache.get_or_compute(key, lambda: (time.sleep(0.15), key)[1])
    threads = [threading.Thread(target=worker, args=(f"k{i}",)) for i in range(4)]
    started = time.monotonic()
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert time.monotonic() - started < 0.35
