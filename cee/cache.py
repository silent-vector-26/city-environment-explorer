from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from cee.sources import AirNowError, load_live_observations

REFRESH_SECONDS = 3600
RETRY_SECONDS = 300


class LiveDataCache:
    """In-process snapshot of AirNow observations, refreshed by a background thread.

    AirNow's hourly-data service can take over a minute, so requests never call it
    directly. They read the last good snapshot, which is kept if a refresh fails.
    """

    def __init__(
        self,
        loader: Callable[[str], pd.DataFrame] = load_live_observations,
        refresh_seconds: float = REFRESH_SECONDS,
        retry_seconds: float = RETRY_SECONDS,
    ) -> None:
        self._loader = loader
        self._refresh_seconds = refresh_seconds
        self._retry_seconds = retry_seconds
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._started = False
        self._data: pd.DataFrame | None = None
        self._error: str | None = None
        self._updated_at: datetime | None = None

    def refresh(self, api_key: str) -> bool:
        try:
            data = self._loader(api_key)
        except AirNowError as exc:
            with self._lock:
                self._error = str(exc)
            return False
        with self._lock:
            self._data = data
            self._error = None
            self._updated_at = datetime.now(timezone.utc)
        return True

    def start(self, api_key: str) -> None:
        """Start the refresh loop once per process; later calls are no-ops."""
        with self._lock:
            if self._started:
                return
            self._started = True
        threading.Thread(
            target=self._run, args=(api_key,), name="airnow-refresh", daemon=True
        ).start()

    def _run(self, api_key: str) -> None:
        while True:
            succeeded = self.refresh(api_key)
            self._ready.set()
            time.sleep(self._refresh_seconds if succeeded else self._retry_seconds)

    def wait_until_ready(self, timeout: float) -> bool:
        return self._ready.wait(timeout)

    def snapshot(self) -> tuple[pd.DataFrame | None, str | None, datetime | None]:
        with self._lock:
            return self._data, self._error, self._updated_at


live_cache = LiveDataCache()
