"""Phase 1 tests — Databricks connection smoke tests.

These verify that .env is loaded and the SDK client can authenticate.
Run after setting up .env with valid credentials.

Usage: pytest tests/test_config.py -v
"""

import pytest


def test_databricks_connection():
    """Verify .env is loaded and SDK client can authenticate."""
    from src.config import db_client

    # Should not raise — proves token + host are valid
    clusters = db_client.clusters.list()
    assert clusters is not None


def test_env_variables_loaded():
    """Verify all required .env variables are set (non-empty)."""
    from src.config import CATALOG, GENIE_SPACE_ID, SCHEMA, VS_ENDPOINT, VS_INDEX

    assert GENIE_SPACE_ID, "GENIE_SPACE_ID is empty — set it in .env"
    assert VS_INDEX, "VECTOR_SEARCH_INDEX is empty — set it in .env"
    assert VS_ENDPOINT, "VECTOR_SEARCH_ENDPOINT is empty — set it in .env"
    assert CATALOG, "DATABRICKS_CATALOG is empty — set it in .env"
    assert SCHEMA, "DATABRICKS_SCHEMA is empty — set it in .env"
