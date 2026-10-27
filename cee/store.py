"""Durable storage of hourly AirNow readings in Azure Cosmos DB (NoSQL API).

This is the second cache level. Documents are keyed by monitoring site and UTC hour,
so saving the same hour again replaces it, which is what we want because AirNow
revises provisional values. The container has a default TTL, so old hours expire
without any cleanup code.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Protocol

import pandas as pd

logger = logging.getLogger(__name__)

DATABASE = "cee"
CONTAINER = "hourly_pm25"
COLUMNS = ["site", "latitude", "longitude", "utc", "value", "agency", "site_code"]


class HourlyStore(Protocol):
    def load(self, since: datetime) -> pd.DataFrame: ...

    def save(self, hourly: pd.DataFrame) -> None: ...


def to_documents(hourly: pd.DataFrame) -> list[dict[str, Any]]:
    documents = []
    for row in hourly.itertuples(index=False):
        utc = pd.Timestamp(row.utc).tz_convert("UTC")
        partition = row.site_code or row.site
        documents.append(
            {
                "id": f"{partition}|{utc.strftime('%Y%m%dT%H')}",
                "pk": partition,
                "site": row.site,
                "site_code": row.site_code,
                "latitude": float(row.latitude),
                "longitude": float(row.longitude),
                "utc": utc.isoformat(),
                "value": float(row.value),
                "agency": row.agency,
            }
        )
    return documents


def from_documents(documents: list[dict[str, Any]]) -> pd.DataFrame:
    if not documents:
        return pd.DataFrame(columns=COLUMNS)
    frame = pd.DataFrame.from_records(documents)
    frame["utc"] = pd.to_datetime(frame["utc"], utc=True)
    return frame[COLUMNS]


class CosmosHourlyStore:
    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint
        self._container: Any = None

    def _get_container(self) -> Any:
        if self._container is None:
            from azure.cosmos import CosmosClient
            from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

            is_production = os.getenv("APP_ENV", "development").lower() == "production"
            credential = (
                ManagedIdentityCredential() if is_production else DefaultAzureCredential()
            )
            client = CosmosClient(self._endpoint, credential=credential)
            self._container = client.get_database_client(DATABASE).get_container_client(
                CONTAINER
            )
        return self._container

    def load(self, since: datetime) -> pd.DataFrame:
        items = self._get_container().query_items(
            query="SELECT * FROM c WHERE c.utc >= @since",
            parameters=[{"name": "@since", "value": pd.Timestamp(since).isoformat()}],
            enable_cross_partition_query=True,
        )
        return from_documents(list(items))

    def save(self, hourly: pd.DataFrame) -> None:
        container = self._get_container()
        for document in to_documents(hourly):
            container.upsert_item(document)


def get_store() -> HourlyStore | None:
    endpoint = os.getenv("COSMOS_ENDPOINT", "").strip()
    return CosmosHourlyStore(endpoint) if endpoint else None
