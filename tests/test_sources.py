from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from cee.sources import (
    AirNowError,
    fetch_hourly_pm25,
    hourly_to_daily,
    parse_hourly_records,
)


def record(utc: str, value: float, site: str = "ASHBURN", code: str = "511071005"):
    return {
        "Latitude": 39.02,
        "Longitude": -77.49,
        "UTC": utc,
        "Parameter": "PM2.5",
        "Unit": "UG/M3",
        "Value": value,
        "SiteName": site,
        "AgencyName": "Virginia DEQ",
        "FullAQSCode": code,
    }


def full_day(day: int, value: float):
    # Hours 05-23 UTC and 00-04 UTC next day cover one local (EDT) day in October.
    return [record(f"2026-10-{day:02d}T{hour:02d}:00", value) for hour in range(4, 24)]


def test_parse_drops_missing_sentinels_and_bad_rows():
    frame = parse_hourly_records(
        [record("2026-10-20T12:00", 5.0), record("2026-10-20T13:00", -999), {"bad": 1}]
    )
    assert list(frame["value"]) == [5.0]
    assert frame["site"].iloc[0] == "Ashburn"


def test_daily_requires_enough_hours_and_labels_records():
    records = full_day(20, 6.0) + [record("2026-10-21T12:00", 40.0)]
    daily = hourly_to_daily(parse_hourly_records(records))
    assert len(daily) == 1
    row = daily.iloc[0]
    assert row["value"] == 6.0
    assert row["record_type"] == "observed"
    assert "AirNow" in row["source"]


def test_fetch_requires_key():
    with pytest.raises(AirNowError):
        fetch_hourly_pm25("  ")


def test_fetch_error_does_not_leak_api_key():
    secret = "SECRET-KEY-123"
    failure = requests.ConnectionError(f"https://x/?API_KEY={secret}")
    with patch("cee.sources.requests.get", side_effect=failure):
        with pytest.raises(AirNowError) as excinfo:
            fetch_hourly_pm25(secret, now=datetime(2026, 10, 26, tzinfo=timezone.utc))
    assert secret not in str(excinfo.value)


def test_fetch_parses_response():
    response = MagicMock()
    response.json.return_value = [record("2026-10-20T12:00", 5.0)]
    with patch("cee.sources.requests.get", return_value=response) as get:
        frame = fetch_hourly_pm25("key", now=datetime(2026, 10, 26, tzinfo=timezone.utc))
    assert len(frame) == 1
    assert get.call_args.kwargs["timeout"] > 0
