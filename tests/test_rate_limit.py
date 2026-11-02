from emporio.rate_limit import RateLimiter
from tests.fakes import FakeClock


def test_allows_up_to_the_limit_then_blocks():
    limiter = RateLimiter(limit=3, window_seconds=60, clock=FakeClock())
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]


def test_window_slides():
    clock = FakeClock()
    limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)
    limiter.allow("a")
    clock.now = 30
    limiter.allow("a")
    assert limiter.allow("a") is False
    clock.now = 60  # the first hit left the window
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False


def test_rejected_hits_do_not_extend_the_block():
    clock = FakeClock()
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.allow("a")
    for second in range(1, 60):  # keeps trying during the window
        clock.now = second
        limiter.allow("a")
    clock.now = 60
    assert limiter.allow("a") is True


def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window_seconds=60, clock=FakeClock())
    assert limiter.allow("a") and limiter.allow("b")
    assert not limiter.allow("a")
