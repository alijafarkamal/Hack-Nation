"""Local data utilities for care-india (optional CSV fallback, city hints).

The primary data source is the Delta table `india_facilities` in Unity Catalog.
This module can load the hackathon CSV from disk for offline map/planner UIs.
"""

import os
from pathlib import Path

# Optional: map common city names → state when `state_normalized` is missing in SQL detail rows.
# Extend as needed for your cleaning pipeline.
CITY_TO_STATE: dict[str, str] = {}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_facilities_csv() -> Path | None:
    """Path to the India dataset CSV in the repo, if present."""
    candidates = list(project_root().glob("VF_*.csv"))
    if not candidates:
        return None
    return candidates[0]
