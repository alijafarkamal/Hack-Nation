"""Databricks client setup — loads .env and initializes SDK clients.

Provides:
 - db_client: WorkspaceClient for Genie, Model Serving, SQL
 - vs_client: VectorSearchClient for semantic search
 - Configuration constants from .env

When Databricks credentials are not configured, the Streamlit/CLI can still start
if only local code paths are used; Databricks calls fail at runtime with clear errors.
"""

import logging
import os

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN", "")

# MLflow: point at Databricks when creds are present
if DATABRICKS_HOST and DATABRICKS_TOKEN:
    try:
        mlflow.set_tracking_uri("databricks")
        os.environ.setdefault("DATABRICKS_HOST", DATABRICKS_HOST)
        os.environ.setdefault("DATABRICKS_TOKEN", DATABRICKS_TOKEN)
        mlflow.set_experiment(
            os.getenv("MLFLOW_EXPERIMENT_PATH", "/Shared/india-medical-agent")
        )
    except Exception as e:
        logger.warning("MLflow Databricks setup failed (will use local): %s", e)
        mlflow.set_tracking_uri("mlruns")
else:
    logger.info(
        "Databricks credentials not found in .env — MLflow will use local tracking."
    )
    mlflow.set_tracking_uri("mlruns")

db_client = WorkspaceClient(
    host=DATABRICKS_HOST or "https://placeholder.cloud.databricks.com",
    token=DATABRICKS_TOKEN or "dapi_placeholder",
)

try:
    vs_client = VectorSearchClient(
        workspace_url=DATABRICKS_HOST or "https://placeholder.cloud.databricks.com",
        personal_access_token=DATABRICKS_TOKEN or "dapi_placeholder",
        disable_notice=True,
    )
except Exception:  # pragma: no cover
    vs_client = None  # type: ignore[assignment]

# Configuration constants
GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID")
VS_INDEX = os.getenv("VECTOR_SEARCH_INDEX")
VS_ENDPOINT = os.getenv("VECTOR_SEARCH_ENDPOINT")
CATALOG = os.getenv("DATABRICKS_CATALOG", "hack_nation")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "india_medical")
TABLE_FACILITIES = "india_facilities"

# Model Serving
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "databricks-qwen3-next-80b-a3b-instruct")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
