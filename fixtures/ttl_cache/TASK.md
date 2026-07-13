# Python TTL cache task

Implement `TTLCache.get_or_compute(key, factory)` in `ttl_cache.py`.

Required behavior:
- Return cached values for hits before their TTL expires.
- Recompute values after TTL expiration.
- Be thread-safe.
- Use per-key single-flight: concurrent calls for the same missing/expired key must run `factory` once, and waiters receive that result.
- Exceptions from `factory` must propagate to callers and must not be cached.
- Calls for different keys must not be unnecessarily serialized.

Run `python -m pytest public_tests` to check the public tests.
