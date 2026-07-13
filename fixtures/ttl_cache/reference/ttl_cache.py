import threading
import time


class TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._values = {}
        self._inflight = {}

    def get_or_compute(self, key, factory):
        while True:
            with self._lock:
                now = time.monotonic()
                item = self._values.get(key)
                if item is not None:
                    value, expires_at = item
                    if now < expires_at:
                        return value
                event = self._inflight.get(key)
                if event is None:
                    event = threading.Event()
                    self._inflight[key] = event
                    owner = True
                    break
                owner = False
            if not owner:
                event.wait()

        try:
            value = factory()
        except BaseException:
            with self._lock:
                self._inflight.pop(key).set()
            raise
        with self._lock:
            self._values[key] = (value, time.monotonic() + self.ttl_seconds)
            self._inflight.pop(key).set()
        return value
