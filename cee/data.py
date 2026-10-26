from __future__ import annotations

from datetime import date, timedelta
from math import cos, pi, sin
from typing import Any

import pandas as pd

MEASURE = "PM2.5 24-hour average"
UNIT = "ug/m3"
SAMPLE_SOURCE = "Synthetic sample data"

LOCATIONS: tuple[dict[str, Any], ...] = (
    {"name": "Annandale", "latitude": 38.8304, "longitude": -77.1964, "baseline": 7.2},
    {"name": "Fairfax", "latitude": 38.8462, "longitude": -77.3064, "baseline": 8.4},
    {"name": "McLean", "latitude": 38.9339, "longitude": -77.1773, "baseline": 6.8},
    {"name": "Reston", "latitude": 38.9586, "longitude": -77.3570, "baseline": 9.1},
)


def generate_sample_observations(
    days: int = 30, as_of: date | None = None
) -> pd.DataFrame:
    """Create repeatable illustrative readings; these are not real measurements."""
    if days < 1:
        raise ValueError("days must be at least 1")

    end_date = as_of or date.today()
    records: list[dict[str, Any]] = []

    for location_index, location in enumerate(LOCATIONS):
        for day_index in range(days):
            observation_date = end_date - timedelta(days=days - day_index - 1)
            weekly_pattern = 1.4 * sin((day_index * 2 * pi / 7) + location_index * 0.55)
            slow_pattern = 0.7 * cos((day_index * 0.2) + location_index)
            value = round(max(1.0, location["baseline"] + weekly_pattern + slow_pattern), 1)
            records.append(
                {
                    "location": location["name"],
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "date": observation_date,
                    "measure": MEASURE,
                    "value": value,
                    "unit": UNIT,
                    "source": SAMPLE_SOURCE,
                    "record_type": "illustrative",
                }
            )

    return pd.DataFrame.from_records(records)


def summarize_evidence(observations: pd.DataFrame) -> list[dict[str, Any]]:
    """Build compact, traceable evidence records for the selected observations."""
    evidence: list[dict[str, Any]] = []

    for evidence_index, (location_name, group) in enumerate(
        observations.groupby("location", sort=True), start=1
    ):
        ordered = group.sort_values("date")
        values = ordered["value"].astype(float)
        window_size = max(1, min(7, len(values) // 2))
        earlier_mean = float(values.iloc[:window_size].mean())
        recent_mean = float(values.iloc[-window_size:].mean())

        evidence.append(
            {
                "evidence_id": f"S{evidence_index}",
                "location": location_name,
                "measure": str(ordered["measure"].iloc[0]),
                "unit": str(ordered["unit"].iloc[0]),
                "start_date": ordered["date"].iloc[0],
                "end_date": ordered["date"].iloc[-1],
                "observation_count": int(len(ordered)),
                "mean_value": float(values.mean()),
                "min_value": float(values.min()),
                "max_value": float(values.max()),
                "earlier_mean": earlier_mean,
                "recent_mean": recent_mean,
                "change": recent_mean - earlier_mean,
                "comparison_window_days": window_size,
                "source": str(ordered["source"].iloc[0]),
                "record_type": str(ordered["record_type"].iloc[0]),
            }
        )

    return evidence


def build_sample_summary(evidence: list[dict[str, Any]]) -> str:
    """Create an explicitly non-AI fallback using only the supplied evidence."""
    if not evidence:
        return "There is not enough selected data to create a summary."

    measure = evidence[0]["measure"]
    unit = evidence[0]["unit"]
    period_start = min(item["start_date"] for item in evidence)
    period_end = max(item["end_date"] for item in evidence)
    all_values = [
        item["mean_value"] for item in evidence if item["observation_count"] > 0
    ]
    overall_mean = sum(all_values) / len(all_values)
    lines = [
        (
            f"Across {len(evidence)} selected locations, the mean {measure} "
            f"was {overall_mean:.1f} {unit} from {period_start} through {period_end}."
        )
    ]

    for item in evidence:
        direction = "increased" if item["change"] > 0.1 else (
            "decreased" if item["change"] < -0.1 else "was broadly steady"
        )
        lines.append(
            f"[{item['evidence_id']}] {item['location']}: mean "
            f"{item['mean_value']:.1f} {unit}; the recent "
            f"{item['comparison_window_days']}-day mean {direction} by "
            f"{abs(item['change']):.1f} {unit} versus the initial window."
        )

    lines.append("These values are synthetic illustrations, not environmental measurements.")
    return "\n\n".join(lines)
