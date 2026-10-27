from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import requests

from cee.telemetry import tracer
AIRNOW_DATA_URL = "https://www.airnowapi.org/aq/data/"
AIRNOW_SOURCE = "EPA AirNow monitoring sites (provisional, unvalidated)"
LIVE_MEASURE = "PM2.5 daily mean of hourly readings"
LIVE_UNIT = "ug/m3"
LOCAL_TIMEZONE = "America/New_York"
# Bounding box around Fairfax County, VA: west, south, east, north.
FAIRFAX_BBOX = (-77.55, 38.60, -77.05, 39.10)
MIN_HOURS_PER_DAY = 18


class AirNowError(RuntimeError):
    """Raised when AirNow data cannot be retrieved or understood."""


def fetch_hourly_pm25(
    api_key: str,
    days: int = 30,
    bbox: tuple[float, float, float, float] = FAIRFAX_BBOX,
    now: datetime | None = None,
    timeout: float = 90.0,
) -> pd.DataFrame:
    if not api_key.strip():
        raise AirNowError("AIRNOW_API_KEY is not set.")

    end = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    params = {
        "startDate": start.strftime("%Y-%m-%dT%H"),
        "endDate": end.strftime("%Y-%m-%dT%H"),
        "parameters": "PM25",
        "BBOX": ",".join(str(value) for value in bbox),
        "dataType": "C",
        "format": "application/json",
        "verbose": "1",
        "monitorType": "0",
        "includerawconcentrations": "0",
        "API_KEY": api_key,
    }
    payload: Any = None
    for attempt in range(2):
        try:
            response = requests.get(AIRNOW_DATA_URL, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.RequestException, ValueError) as exc:
            if attempt == 1:
                # Do not echo the exception text: it can include the request URL and API key.
                raise AirNowError(
                    f"AirNow request failed ({type(exc).__name__})."
                ) from None

    if not isinstance(payload, list):
        raise AirNowError("AirNow returned an unexpected response.")
    return parse_hourly_records(payload)


def _clean_site_name(name: str) -> str:
    name = name.strip()
    return name.title() if name.isupper() else name


def parse_hourly_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    columns = ["site", "latitude", "longitude", "utc", "value", "agency", "site_code"]
    rows = []
    for record in records:
        try:
            value = float(record["Value"])
            rows.append(
                {
                    "site": _clean_site_name(str(record["SiteName"])),
                    "latitude": float(record["Latitude"]),
                    "longitude": float(record["Longitude"]),
                    "utc": pd.Timestamp(record["UTC"], tz="UTC"),
                    "value": value,
                    "agency": str(record.get("AgencyName", "")),
                    "site_code": str(record.get("FullAQSCode", "")),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    frame = pd.DataFrame.from_records(rows, columns=columns)
    # AirNow uses negative sentinel values for missing readings.
    return frame.loc[frame["value"] >= 0].drop_duplicates(["site_code", "utc"])


def hourly_to_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to local-day means, keeping only days with enough hourly readings."""
    columns = [
        "location", "latitude", "longitude", "date", "measure", "value",
        "unit", "source", "record_type", "hours",
    ]
    if hourly.empty:
        return pd.DataFrame(columns=columns)

    local = hourly.assign(
        date=hourly["utc"].dt.tz_convert(LOCAL_TIMEZONE).dt.date
    )
    daily = (
        local.groupby(["site", "latitude", "longitude", "date"], as_index=False)
        .agg(value=("value", "mean"), hours=("value", "size"))
    )
    daily = daily.loc[daily["hours"] >= MIN_HOURS_PER_DAY].copy()
    daily["value"] = daily["value"].round(1)
    daily = daily.rename(columns={"site": "location"})
    daily["measure"] = LIVE_MEASURE
    daily["unit"] = LIVE_UNIT
    daily["source"] = AIRNOW_SOURCE
    daily["record_type"] = "observed"
    return daily[columns].sort_values(["location", "date"]).reset_index(drop=True)


def load_live_observations(api_key: str, days: int = 30) -> pd.DataFrame:
    with tracer.start_as_current_span("cee.load_airnow") as span:
        span.set_attribute("cee.days", days)
        daily = hourly_to_daily(fetch_hourly_pm25(api_key, days=days))
        span.set_attribute("cee.daily_rows", len(daily))
        if daily.empty:
            raise AirNowError("AirNow returned no usable PM2.5 readings.")
        return daily
