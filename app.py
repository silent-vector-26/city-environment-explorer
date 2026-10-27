from __future__ import annotations

import math
import os
from datetime import date, timedelta
from typing import Any

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from azure.core.exceptions import AzureError
from dotenv import load_dotenv
from openai import OpenAIError
from streamlit_folium import st_folium

from cee.ai import azure_ai_is_configured, generate_grounded_summary
from cee.cache import live_cache
from cee.data import (
    LOCATIONS,
    MEASURE as SAMPLE_MEASURE,
    SAMPLE_SOURCE,
    UNIT,
    build_sample_summary,
    generate_sample_observations,
    summarize_evidence,
)

load_dotenv()

st.set_page_config(
    page_title="Fairfax County City Environment Explorer",
    layout="wide",
)


def nearest_location(
    clicked: dict[str, Any] | None, locations: list[dict[str, Any]]
) -> str | None:
    if not clicked:
        return None
    try:
        clicked_lat = float(clicked["lat"])
        clicked_lon = float(clicked["lng"])
    except (KeyError, TypeError, ValueError):
        return None

    nearest = min(
        locations,
        key=lambda item: math.hypot(
            (item["latitude"] - clicked_lat) * 111,
            (item["longitude"] - clicked_lon)
            * 111
            * math.cos(math.radians(clicked_lat)),
        ),
    )
    distance_km = math.hypot(
        (nearest["latitude"] - clicked_lat) * 111,
        (nearest["longitude"] - clicked_lon)
        * 111
        * math.cos(math.radians(clicked_lat)),
    )
    return nearest["name"] if distance_km < 3.0 else None


def make_map(
    observations: pd.DataFrame, locations: list[dict[str, Any]], is_live: bool
) -> folium.Map:
    county_map = folium.Map(
        location=[38.86, -77.28],
        zoom_start=10,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    for location in locations:
        latest = observations.loc[
            observations["location"] == location["name"]
        ].sort_values("date").tail(1)
        latest_value = float(latest["value"].iloc[0])
        latest_date = latest["date"].iloc[0]
        note = (
            "AirNow monitoring site; provisional daily mean."
            if is_live
            else "Synthetic sample; not a monitoring station."
        )
        popup = (
            f"{location['name']}<br>"
            f"PM2.5 on {latest_date}: {latest_value:.1f} {UNIT}<br>{note}"
        )
        folium.CircleMarker(
            location=[location["latitude"], location["longitude"]],
            radius=8,
            color="#126e82",
            fill=True,
            fill_color="#20a4a9",
            fill_opacity=0.85,
            tooltip=location["name"],
            popup=folium.Popup(popup, max_width=260),
        ).add_to(county_map)
    return county_map


def load_observations() -> tuple[pd.DataFrame, bool, str | None]:
    api_key = os.getenv("AIRNOW_API_KEY", "").strip()
    if not api_key:
        return generate_sample_observations(), False, None
    live_cache.start(api_key)
    with st.spinner("Loading AirNow readings (first load can take up to a minute)..."):
        live_cache.wait_until_ready(timeout=120)
    data, error, _ = live_cache.snapshot()
    if data is not None:
        return data, True, None
    return (
        generate_sample_observations(),
        False,
        error or "AirNow data is still loading; refresh in a minute.",
    )


observations, is_live, live_error = load_observations()
if is_live:
    locations = (
        observations.groupby("location", sort=True)[["latitude", "longitude"]]
        .first()
        .reset_index()
        .rename(columns={"location": "name"})
        .to_dict("records")
    )
    measure = str(observations["measure"].iloc[0])
    source = str(observations["source"].iloc[0])
else:
    locations = list(LOCATIONS)
    measure = SAMPLE_MEASURE
    source = SAMPLE_SOURCE
location_options = [item["name"] for item in locations]
st.session_state["selected_locations"] = [
    name
    for name in st.session_state.get("selected_locations", location_options[:2])
    if name in location_options
] or location_options[:2]

st.title("Fairfax County City Environment Explorer")
if is_live:
    st.caption(
        "Explore recent PM2.5 readings from air-quality monitors in and around "
        "Fairfax County."
    )
    st.info(
        "**Real monitoring data:** hourly PM2.5 readings from EPA AirNow monitoring "
        "sites, averaged by local day. Data are provisional and unvalidated, may be "
        "revised, and are not a health or safety assessment."
    )
else:
    st.caption("Explore sample air-quality trends and compare locations.")
    if live_error:
        st.error(f"Could not load AirNow data, showing sample data instead: {live_error}")
    st.warning(
        "**Sample data only:** Every plotted PM2.5 value and map point is generated "
        "for demonstration. They are not measurements, forecasts, or live monitoring."
    )

try:
    ai_configured = azure_ai_is_configured()
except RuntimeError as exc:
    st.error(f"Azure AI configuration error: {exc}")
    st.stop()

st.subheader("Explore the map")
st.caption(
    "Pan or zoom the map. Select a marker to inspect its latest value; "
    "click a marker to focus the location in the filters."
)
map_state = st_folium(
    make_map(observations, locations, is_live),
    height=390,
    use_container_width=True,
    returned_objects=["last_object_clicked"],
    key="fairfax_live_map" if is_live else "fairfax_sample_map",
)
clicked_location = nearest_location(map_state.get("last_object_clicked"), locations)
if clicked_location:
    click_key = clicked_location
    if st.session_state.get("last_map_selection") != click_key:
        st.session_state["last_map_selection"] = click_key
        st.session_state["selected_locations"] = [clicked_location]

with st.sidebar:
    st.header("Explore the data" if is_live else "Explore the sample")
    selected_locations = st.multiselect(
        "Monitoring sites" if is_live else "Locations",
        options=location_options,
        key="selected_locations",
        help="Choose one or more locations for trends and comparison.",
    )
    days = st.slider("Time range (days)", min_value=7, max_value=30, value=30)
    st.divider()
    if ai_configured:
        st.success("Azure AI summary is configured.")
        st.caption("A summary request sends the selected evidence to your Azure model.")
    else:
        st.info("Azure AI is optional and not configured.")
        st.caption(
            "Without Azure credentials, the summary button uses a deterministic "
            "fallback, not an AI model."
        )

if not selected_locations:
    st.info("Select at least one location to explore its data.")
    st.stop()

latest_date = observations["date"].max()
first_date = latest_date - timedelta(days=days - 1)
filtered = observations.loc[
    observations["location"].isin(selected_locations)
    & (observations["date"] >= first_date)
    & (observations["date"] <= latest_date)
].copy()
evidence = summarize_evidence(filtered)
summary_signature = (
    tuple(sorted(selected_locations)),
    days,
    latest_date.isoformat(),
)

st.caption(
    f"Measure: {measure} ({UNIT}) | Period: {first_date} to {latest_date} "
    f"| Source: {source}"
)

if filtered.empty:
    st.info("No readings are available for the selected sites and time range.")
    st.stop()

latest_rows = filtered.sort_values("date").groupby("location").tail(1)
mean_latest = float(latest_rows["value"].mean())
metric_cols = st.columns(3)
metric_cols[0].metric(
    "Latest daily mean" if is_live else "Latest sample mean",
    f"{mean_latest:.1f} {UNIT}",
)
metric_cols[1].metric("Locations selected", len(selected_locations))
metric_cols[2].metric("Daily records" if is_live else "Illustrative records", len(filtered))

st.subheader("Trends over time")
trend_fig = px.line(
    filtered,
    x="date",
    y="value",
    color="location",
    markers=True,
    labels={"date": "Observation date", "value": f"{measure} ({UNIT})"},
)
trend_fig.update_layout(
    legend_title_text="Monitoring site" if is_live else "Illustrative location"
)
st.plotly_chart(trend_fig, width="stretch")

st.subheader("Compare locations")
if len(evidence) > 1:
    comparison = pd.DataFrame(evidence)
    comparison_fig = px.bar(
        comparison,
        x="location",
        y="mean_value",
        color="location",
        labels={
            "location": "Monitoring site" if is_live else "Illustrative location",
            "mean_value": f"Mean {measure} ({UNIT})",
        },
    )
    comparison_fig.update_layout(showlegend=False)
    st.plotly_chart(comparison_fig, width="stretch")
else:
    st.info("Select at least two locations to compare their averages.")

st.subheader("Grounded summary")
st.write(
    "The summary is limited to the selected records. Evidence is shown below."
)
if st.button("Generate summary", type="primary"):
    if ai_configured:
        try:
            st.session_state["summary_result"] = {
                "signature": summary_signature,
                "kind": "Azure AI-generated summary",
                "text": generate_grounded_summary(evidence),
            }
        except (ValueError, RuntimeError) as exc:
            st.error(f"Could not generate a grounded summary: {exc}")
        except (AzureError, OpenAIError) as exc:
            st.error(f"Azure AI request failed: {exc}")
    else:
        st.session_state["summary_result"] = {
            "signature": summary_signature,
            "kind": "Deterministic fallback (not AI-generated)",
            "text": build_sample_summary(evidence),
        }

summary_result = st.session_state.get("summary_result")
if summary_result:
    if summary_result["signature"] == summary_signature:
        st.info(summary_result["kind"])
        st.markdown(summary_result["text"])
    else:
        st.caption("Selections changed; generate a new summary for this view.")

st.subheader("Evidence")
location_label = "Monitoring site" if is_live else "Illustrative location"
evidence_frame = pd.DataFrame(evidence).rename(
    columns={
        "evidence_id": "Evidence ID",
        "location": location_label,
        "measure": "Measure",
        "unit": "Unit",
        "start_date": "Period start",
        "end_date": "Period end",
        "observation_count": "Records",
        "mean_value": "Mean",
        "min_value": "Minimum",
        "max_value": "Maximum",
        "initial_window_mean": "Initial-window mean",
        "recent_window_mean": "Recent-window mean",
        "change": "Recent vs initial window",
        "comparison_window_days": "Comparison window (days)",
        "source": "Source",
        "record_type": "Record type",
    }
)
st.dataframe(
    evidence_frame[
        [
            "Evidence ID",
            location_label,
            "Period start",
            "Period end",
            "Records",
            "Mean",
            "Minimum",
            "Maximum",
            "Initial-window mean",
            "Recent-window mean",
            "Comparison window (days)",
            "Source",
        ]
    ],
    width="stretch",
    hide_index=True,
)
if is_live:
    st.caption(
        "Evidence records summarize provisional EPA AirNow readings and may be revised."
    )
else:
    st.caption(
        "Evidence records summarize generated sample values. No live data was "
        "available for this view."
    )
