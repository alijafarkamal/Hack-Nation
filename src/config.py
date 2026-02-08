"""Databricks client setup — loads .env and initializes SDK clients.

Provides:
  - db_client: WorkspaceClient for Genie, Model Serving, SQL
  - vs_client: VectorSearchClient for semantic search
  - Configuration constants from .env

Ref: https://docs.databricks.com/en/dev-tools/sdk-python.html
"""

import os

import mlflow
from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient
from dotenv import load_dotenv

load_dotenv()

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")

# Point MLflow at Databricks so traces appear in the Experiments UI
mlflow.set_tracking_uri("databricks")
os.environ.setdefault("DATABRICKS_HOST", DATABRICKS_HOST or "")
os.environ.setdefault("DATABRICKS_TOKEN", DATABRICKS_TOKEN or "")
mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_PATH", "/Shared/ghana-medical-agent"))

db_client = WorkspaceClient(host=DATABRICKS_HOST, token=DATABRICKS_TOKEN)

vs_client = VectorSearchClient(
    workspace_url=DATABRICKS_HOST,
    personal_access_token=DATABRICKS_TOKEN,
    disable_notice=True,
)

GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID")
VS_INDEX = os.getenv("VECTOR_SEARCH_INDEX")
VS_ENDPOINT = os.getenv("VECTOR_SEARCH_ENDPOINT")
CATALOG = os.getenv("DATABRICKS_CATALOG")
SCHEMA = os.getenv("DATABRICKS_SCHEMA")

# Model Serving endpoint name
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "databricks-qwen3-next-80b-a3b-instruct")
