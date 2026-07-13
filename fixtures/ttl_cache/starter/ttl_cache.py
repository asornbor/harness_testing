import time


class TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._values = {}

    def get_or_compute(self, key, factory):
        now = time.monotonic()
        item = self._values.get(key)
        if item is not None:
            value, expires_at = item
            if now < expires_at:
                return value
        value = factory()
        self._values[key] = (value, time.monotonic() + self.ttl_seconds)
        return value
