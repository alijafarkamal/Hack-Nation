"""Databricks client setup — loads .env and initializes the SDK WorkspaceClient.

Ref: https://docs.databricks.com/en/dev-tools/sdk-python.html
"""

from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
import os

load_dotenv()

db_client = WorkspaceClient(
    host=os.getenv("DATABRICKS_HOST"),
    token=os.getenv("DATABRICKS_TOKEN"),
)

GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID")
VS_INDEX = os.getenv("VECTOR_SEARCH_INDEX")
VS_ENDPOINT = os.getenv("VECTOR_SEARCH_ENDPOINT")
CATALOG = os.getenv("DATABRICKS_CATALOG")
SCHEMA = os.getenv("DATABRICKS_SCHEMA")
