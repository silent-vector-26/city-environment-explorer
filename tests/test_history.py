from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from cee.cache import LiveDataCache
from cee.history import OVERLAP_HOURS, load_stored_daily, load_with_history
from cee.sources import AirNowError
from cee.store import COLUMNS, from_documents, to_documents

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


def hourly(start: datetime, hours: int, value: float = 5.0, site_code: str = "A1") -> pd.DataFrame:
    rows = [
        {
            "site": "Ashburn",
            "latitude": 39.0,
            "longitude": -77.5,
            "utc": pd.Timestamp(start + timedelta(hours=i)),
            "value": value,
            "agency": "VA DEQ",
            "site_code": site_code,
        }
        for i in range(hours)
    ]
    return pd.DataFrame.from_records(rows, columns=COLUMNS)


class MemoryStore:
    def __init__(self, frame: pd.DataFrame | None = None) -> None:
        self.frame = frame if frame is not None else from_documents([])
        self.saved: list[pd.DataFrame] = []

    def load(self, since: datetime) -> pd.DataFrame:
        return self.frame.loc[self.frame["utc"] >= since]

    def save(self, hourly_frame: pd.DataFrame) -> None:
        self.saved.append(hourly_frame)


class BrokenStore:
    def load(self, since: datetime) -> pd.DataFrame:
        raise RuntimeError("cosmos down")

    def save(self, hourly_frame: pd.DataFrame) -> None:
        raise RuntimeError("cosmos down")


def test_document_round_trip_and_idempotent_id() -> None:
    frame = hourly(NOW - timedelta(hours=3), 3)
    documents = to_documents(frame)
    assert len({d["id"] for d in documents}) == 3
    assert documents[0]["id"] == "A1|20261027T09"
    restored = from_documents(documents)
    assert list(restored["value"]) == [5.0, 5.0, 5.0]
    assert str(restored["utc"].dt.tz) == "UTC"


def test_empty_store_fetches_full_window() -> None:
    calls = []

    def fetch(_key: str, start: datetime, now: datetime) -> pd.DataFrame:
        calls.append(start)
        return hourly(start, 24 * 3)

    load_with_history("k", MemoryStore(), days=30, now=NOW, fetch=fetch)
    assert calls == [NOW - timedelta(days=30)]


def test_fetch_starts_at_newest_stored_hour_minus_overlap() -> None:
    newest = NOW - timedelta(hours=10)
    store = MemoryStore(hourly(newest - timedelta(hours=100), 101))
    calls = []

    def fetch(_key: str, start: datetime, now: datetime) -> pd.DataFrame:
        calls.append(start)
        return hourly(start, 5)

    load_with_history("k", store, days=30, now=NOW, fetch=fetch)
    assert calls == [newest - timedelta(hours=OVERLAP_HOURS)]
    assert len(store.saved) == 1


def test_fetch_start_never_precedes_window() -> None:
    old = NOW - timedelta(days=45)
    store = MemoryStore(hourly(old, 5))
    calls = []

    def fetch(_key: str, start: datetime, now: datetime) -> pd.DataFrame:
        calls.append(start)
        return hourly(start, 24 * 3)

    load_with_history("k", store, days=30, now=NOW, fetch=fetch)
    assert calls == [NOW - timedelta(days=30)]


def test_revised_values_replace_stored_ones() -> None:
    day_start = datetime(2026, 10, 25, 4, tzinfo=timezone.utc)
    store = MemoryStore(hourly(day_start, 30, value=5.0))

    def fetch(_key: str, start: datetime, now: datetime) -> pd.DataFrame:
        return hourly(day_start, 30, value=9.0)

    daily = load_with_history("k", store, days=30, now=NOW, fetch=fetch)
    assert set(daily["value"]) == {9.0}


def test_airnow_failure_serves_stored_data() -> None:
    store = MemoryStore(hourly(NOW - timedelta(days=3), 24 * 3))

    def fetch(*_args, **_kwargs) -> pd.DataFrame:
        raise AirNowError("slow")

    assert not load_with_history("k", store, days=30, now=NOW, fetch=fetch).empty


def test_airnow_failure_with_empty_store_raises() -> None:
    def fetch(*_args, **_kwargs) -> pd.DataFrame:
        raise AirNowError("slow")

    with pytest.raises(AirNowError):
        load_with_history("k", MemoryStore(), days=30, now=NOW, fetch=fetch)


def test_store_failure_falls_back_to_full_airnow_fetch() -> None:
    def fetch(_key: str, start: datetime, now: datetime) -> pd.DataFrame:
        return hourly(start, 24 * 3)

    daily = load_with_history("k", BrokenStore(), days=30, now=NOW, fetch=fetch)
    assert not daily.empty
    assert load_stored_daily(BrokenStore(), now=NOW) is None


def test_cache_seeds_from_store_before_first_airnow_call() -> None:
    seeded = pd.DataFrame({"value": [1.0]})
    airnow_called = []

    def loader(_key: str) -> pd.DataFrame:
        airnow_called.append(1)
        return pd.DataFrame({"value": [2.0]})

    cache = LiveDataCache(loader=loader, seed_loader=lambda: seeded)
    cache._seed()
    assert cache.wait_until_ready(timeout=1)
    assert cache.snapshot()[0] is seeded
    assert airnow_called == []


def test_cache_ignores_failing_seed_loader() -> None:
    def seed() -> pd.DataFrame:
        raise RuntimeError("cosmos down")

    cache = LiveDataCache(seed_loader=seed)
    cache._seed()
    assert cache.snapshot()[0] is None
