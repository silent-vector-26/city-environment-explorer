"""Container entry point: warm the AirNow cache, then run Streamlit in this process.

Running Streamlit in the same process lets the cache load at container start
rather than on the first visit.
"""

from __future__ import annotations

import os
import sys

from streamlit.web import cli as stcli

from cee.cache import live_cache
from cee.telemetry import configure_telemetry

if __name__ == "__main__":
    configure_telemetry()
    api_key = os.getenv("AIRNOW_API_KEY", "").strip()
    if api_key:
        live_cache.start(api_key)
    sys.argv = [
        "streamlit",
        "run",
        "app.py",
        "--server.address=0.0.0.0",
        f"--server.port={os.getenv('PORT', '8501')}",
        "--server.headless=true",
    ]
    sys.exit(stcli.main())
