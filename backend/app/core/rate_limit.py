import time
from collections import deque


class SlidingWindowLimiter:
    """In-process limit of `limit` hits per `window_seconds` per key.

    Per API process, which is enough for one container guarding a login endpoint; it is not a
    shared limit across replicas.
    """

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > 10_000:  # bound memory against many distinct keys
            self._hits = {
                k: v for k, v in self._hits.items() if v and now - v[-1] <= self.window_seconds
            }
        return True

    def reset(self) -> None:
        self._hits.clear()
