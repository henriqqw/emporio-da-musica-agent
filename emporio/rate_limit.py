"""Sliding-window rate limit for the demo channel.

In memory and per process: enough to stop a script from brute-forcing the e-mail of a
known phone or burning the LLM quota. A deployment with several instances would keep
the counters in Redis or leave this to the API gateway; the WhatsApp provider also
limits senders on its side.
"""

import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for `key` and say whether it is within the limit.

        Rejected hits are not recorded, so a client that waits gets through again.
        """
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True
