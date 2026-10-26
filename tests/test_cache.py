import threading

import pandas as pd

from cee.cache import LiveDataCache
from cee.sources import AirNowError


def test_refresh_stores_snapshot_and_keeps_last_good_on_failure():
    frame = pd.DataFrame({"value": [1.0]})
    results = [frame, AirNowError("boom")]

    def loader(_key: str) -> pd.DataFrame:
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    cache = LiveDataCache(loader=loader)
    assert cache.refresh("key") is True
    assert cache.refresh("key") is False

    data, error, updated_at = cache.snapshot()
    assert data is frame
    assert error == "boom"
    assert updated_at is not None


def test_start_is_idempotent_and_signals_ready():
    calls = []
    done = threading.Event()

    def loader(_key: str) -> pd.DataFrame:
        calls.append(1)
        done.set()
        return pd.DataFrame({"value": [1.0]})

    cache = LiveDataCache(loader=loader, refresh_seconds=3600)
    cache.start("key")
    cache.start("key")

    assert cache.wait_until_ready(timeout=5)
    assert len(calls) == 1
    assert cache.snapshot()[0] is not None
