import time
from ttl_cache import TTLCache


def test_hit_and_expiration():
    cache = TTLCache(ttl_seconds=0.05)
    calls = 0
    def factory():
        nonlocal calls
        calls += 1
        return calls
    assert cache.get_or_compute("a", factory) == 1
    assert cache.get_or_compute("a", factory) == 1
    assert calls == 1
    time.sleep(0.07)
    assert cache.get_or_compute("a", factory) == 2


def test_exception_not_cached():
    cache = TTLCache(ttl_seconds=10)
    calls = 0
    def factory():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("boom")
        return "ok"
    try:
        cache.get_or_compute("x", factory)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    assert cache.get_or_compute("x", factory) == "ok"
