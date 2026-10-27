"""Load AirNow data through a durable store so only new hours are fetched."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

import pandas as pd

from cee.sources import AirNowError, fetch_hourly_pm25, hourly_to_daily
from cee.store import HourlyStore, from_documents
from cee.telemetry import tracer

logger = logging.getLogger(__name__)

# AirNow values are provisional and revised, so re-fetch this much already-stored data.
OVERLAP_HOURS = 48
DEFAULT_DAYS = 30


def _safe_load(store: HourlyStore, since: datetime) -> pd.DataFrame:
    try:
        return store.load(since)
    except Exception:  # storage trouble must degrade to a full AirNow fetch
        logger.exception("Could not read stored hourly data.")
        return from_documents([])


def _safe_save(store: HourlyStore, hourly: pd.DataFrame) -> bool:
    try:
        store.save(hourly)
        return True
    except Exception:
        logger.exception("Could not save hourly data.")
        return False


def load_stored_daily(
    store: HourlyStore, days: int = DEFAULT_DAYS, now: datetime | None = None
) -> pd.DataFrame | None:
    """Daily observations from the store alone, or None when nothing usable is stored."""
    since = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    stored = _safe_load(store, since)
    daily = hourly_to_daily(stored)
    return None if daily.empty else daily


def load_with_history(
    api_key: str,
    store: HourlyStore,
    days: int = DEFAULT_DAYS,
    now: datetime | None = None,
    fetch: Callable[..., pd.DataFrame] = fetch_hourly_pm25,
) -> pd.DataFrame:
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(days=days)

    with tracer.start_as_current_span("cee.load_airnow") as span:
        span.set_attribute("cee.days", days)
        stored = _safe_load(store, window_start)
        span.set_attribute("cee.stored_rows", len(stored))

        if stored.empty:
            fetch_start = window_start
        else:
            fetch_start = max(
                window_start, stored["utc"].max() - timedelta(hours=OVERLAP_HOURS)
            )
        span.set_attribute("cee.fetch_hours", int((now - fetch_start).total_seconds() // 3600))

        try:
            fresh = fetch(api_key, start=fetch_start, now=now)
        except AirNowError:
            if stored.empty:
                raise
            span.set_attribute("cee.served_from_store_only", True)
            hourly = stored
        else:
            span.set_attribute("cee.fetched_rows", len(fresh))
            if not fresh.empty:
                _safe_save(store, fresh)
            frames = [frame for frame in (stored, fresh) if not frame.empty]
            hourly = (
                pd.concat(frames).drop_duplicates(["site_code", "utc"], keep="last")
                if frames
                else fresh
            )

        daily = hourly_to_daily(hourly.loc[hourly["utc"] >= window_start])
        span.set_attribute("cee.daily_rows", len(daily))
        if daily.empty:
            raise AirNowError("AirNow returned no usable PM2.5 readings.")
        return daily
