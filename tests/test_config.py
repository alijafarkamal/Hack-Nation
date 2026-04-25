"""Databricks connectivity — skipped without credentials."""

import os

import pytest

requires_creds = pytest.mark.skipif(
    not (os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN")),
    reason="Set DATABRICKS_HOST and DATABRICKS_TOKEN",
)


@requires_creds
def test_databricks_connection():
    from src.config import db_client

    clusters = db_client.clusters.list()
    assert clusters is not None


@requires_creds
def test_env_variables_loaded():
    from src.config import CATALOG, GENIE_SPACE_ID, SCHEMA, VS_ENDPOINT, VS_INDEX

    assert GENIE_SPACE_ID, "GENIE_SPACE_ID is empty"
    assert VS_INDEX, "VECTOR_SEARCH_INDEX is empty"
    assert VS_ENDPOINT, "VECTOR_SEARCH_ENDPOINT is empty"
    assert CATALOG, "DATABRICKS_CATALOG is empty"
    assert SCHEMA, "DATABRICKS_SCHEMA is empty"
