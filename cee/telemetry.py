"""Optional OpenTelemetry tracing exported to Azure Application Insights.

Spans are always created through the OpenTelemetry API, which is a no-op until an
exporter is configured. Set APPLICATIONINSIGHTS_CONNECTION_STRING to enable
export. Span attributes carry counts, timings and model metadata only; prompts,
evidence text and model output are never recorded.
"""

from __future__ import annotations

import logging
import os

from opentelemetry import trace

logger = logging.getLogger(__name__)
_configured = False

tracer = trace.get_tracer("cee")


def configure_telemetry() -> bool:
    """Enable Azure Monitor export once; return True when export is active."""
    global _configured
    if _configured:
        return True
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection_string:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=connection_string)
    except Exception:  # telemetry must never stop the app from starting
        logger.exception("Could not enable Azure Monitor telemetry.")
        return False
    _configured = True
    return True
