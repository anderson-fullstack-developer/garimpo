"""Limitador simples em memória (vale por processo; com várias réplicas troque por Redis)."""

import time
from collections import defaultdict, deque

from app.errors import ApiError


class RateLimiter:
    def __init__(self, max_events: int, window_seconds: int, message: str):
        self.max_events = max_events
        self.window = window_seconds
        self.message = message
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        while events and now - events[0] > self.window:
            events.popleft()
        return events

    def check(self, key: str) -> None:
        """Levanta 429 se `key` já passou do limite na janela."""
        events = self._prune(key, time.monotonic())
        if len(events) >= self.max_events:
            raise ApiError(429, "RATE_LIMITED", self.message)

    def record(self, key: str) -> None:
        now = time.monotonic()
        self._prune(key, now).append(now)

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)


login_failures = RateLimiter(5, 15 * 60, "Too many attempts. Try again in a few minutes.")
register_limiter = RateLimiter(10, 3600, "Too many sign-ups from this address. Try again later.")
email_limiter = RateLimiter(5, 3600, "Too many requests. Try again later.")


def reset_all() -> None:
    for limiter in (login_failures, register_limiter, email_limiter):
        limiter.reset()
