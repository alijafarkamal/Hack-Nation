#!/usr/bin/env python3
"""Phase 1 — Databricks Setup via SDK (run locally, no browser needed).

This script:
  1. Discovers your SQL warehouse
  2. Creates catalog → schema → volume (if they don't exist)
  3. Uploads the CSV (cleaned locally with pandas → parquet)
  4. Creates a Delta table with clean data
  5. Adds column descriptions for Genie
  6. Creates a Vector Search endpoint + index
  7. Updates your .env with the new values

Usage:
    cd Hack-Nation
    source .venv/bin/activate
    python -u scripts/setup_databricks.py

The only manual step left after this is creating a Genie Space in the UI.
"""

import builtins
import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv, set_key

# Force unbuffered output so progress appears immediately
_original_print = builtins.print


def print(*args, **kwargs):
    kwargs.setdefault("flush", True)
    _original_print(*args, **kwargs)


# ── Load environment ─────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")

if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
    print("ERROR: DATABRICKS_HOST and DATABRICKS_TOKEN must be set in .env")
    sys.exit(1)

# ── SDK Clients ──────────────────────────────────────────────────────────────
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, StatementState

w = WorkspaceClient(host=DATABRICKS_HOST, token=DATABRICKS_TOKEN)

# ── Configuration ────────────────────────────────────────────────────────────
CATALOG = "hack_nation"
SCHEMA = "ghana_medical"
VOLUME = "raw_data"
TABLE_NAME = "ghana_facilities"
TABLE_FQN = f"{CATALOG}.{SCHEMA}.{TABLE_NAME}"
VS_ENDPOINT = "ghana-medical-vs"
VS_INDEX = f"{CATALOG}.{SCHEMA}.ghana_facilities_index"
CSV_PATH = ROOT / "resources" / "Virtue Foundation Ghana v0.3 - Sheet1.csv"


def banner(msg: str):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


# ═════════════════════════════════════════════════════════════════════════════
# Step 0: Discover SQL Warehouse
# ═════════════════════════════════════════════════════════════════════════════
def find_warehouse() -> str:
    """Find a running or startable SQL warehouse and return its ID."""
    banner("Step 0: Discovering SQL warehouse")
    warehouses = list(w.warehouses.list())
    if not warehouses:
        print("ERROR: No SQL warehouses found.")
        print("       Go to SQL Warehouses in the Databricks UI and create one.")
        sys.exit(1)

    for wh in warehouses:
        print(f"  Found: {wh.name} (id={wh.id}, state={wh.state})")

    running = [wh for wh in warehouses if "RUNNING" in str(wh.state)]
    if running:
        chosen = running[0]
    else:
        chosen = warehouses[0]
        print(f"  Starting warehouse '{chosen.name}'...")
        w.warehouses.start(chosen.id)
        for _ in range(30):
            wh = w.warehouses.get(chosen.id)
            if "RUNNING" in str(wh.state):
                break
            print(f"    state: {wh.state} — waiting...")
            time.sleep(10)

    print(f"  Using warehouse: {chosen.name} (id={chosen.id})")
    return chosen.id


def run_sql(warehouse_id: str, sql: str, description: str = "") -> list:
    """Execute a SQL statement and return rows (if any)."""
    if description:
        print(f"  -> {description}")

    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="50s",
        disposition=Disposition.INLINE,
    )

    if resp.status and resp.status.state == StatementState.FAILED:
        error_msg = resp.status.error.message if resp.status.error else "Unknown"
        if "already exists" in error_msg.lower():
            print("     (already exists — skipping)")
            return []
        print(f"     ERROR: {error_msg[:300]}")
        return []

    if resp.result and resp.result.data_array:
        return resp.result.data_array
    return []


# ═════════════════════════════════════════════════════════════════════════════
# Step 1: Create Catalog → Schema → Volume
# ═════════════════════════════════════════════════════════════════════════════
def create_catalog_schema_volume(warehouse_id: str):
    banner("Step 1: Creating catalog, schema, and volume")
    run_sql(warehouse_id, f"CREATE CATALOG IF NOT EXISTS {CATALOG}",
            f"Create catalog: {CATALOG}")
    run_sql(warehouse_id, f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}",
            f"Create schema: {CATALOG}.{SCHEMA}")
    run_sql(warehouse_id,
            f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}",
            f"Create volume: {CATALOG}.{SCHEMA}.{VOLUME}")
    print("  Catalog, schema, and volume ready")


# ═════════════════════════════════════════════════════════════════════════════
# Step 2: Clean CSV locally + upload as Parquet
# ═════════════════════════════════════════════════════════════════════════════
def clean_and_upload() -> str:
    """Clean CSV with pandas, save as parquet, upload to volume."""
    banner("Step 2: Clean CSV locally + upload as Parquet")

    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH)
    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")

    # Rename 'mongo DB' (space not allowed in Delta column names)
    df = df.rename(columns={"mongo DB": "mongo_db"})
    print("  Renamed 'mongo DB' -> 'mongo_db'")

    # Fix 'farmacy' typo
    fixed = (df["facilityTypeId"] == "farmacy").sum()
    df["facilityTypeId"] = df["facilityTypeId"].replace("farmacy", "pharmacy")
    print(f"  Fixed {fixed} 'farmacy' -> 'pharmacy'")

    # Normalize region names
    region_map = {
        "Greater Accra Region": "Greater Accra", "Accra": "Greater Accra",
        "GREATER ACCRA": "Greater Accra", "greater accra": "Greater Accra",
        "Ashanti Region": "Ashanti", "ASHANTI": "Ashanti",
        "Western Region": "Western", "WESTERN": "Western",
        "Central Region": "Central", "CENTRAL": "Central",
        "Eastern Region": "Eastern", "EASTERN": "Eastern",
        "Volta Region": "Volta", "VOLTA": "Volta",
        "Northern Region": "Northern", "NORTHERN": "Northern",
        "Upper East Region": "Upper East", "UPPER EAST": "Upper East",
        "Upper West Region": "Upper West", "UPPER WEST": "Upper West",
        "Bono Region": "Bono", "BONO": "Bono",
        "Bono East Region": "Bono East", "BONO EAST": "Bono East",
        "Ahafo Region": "Ahafo", "AHAFO": "Ahafo",
        "Savannah Region": "Savannah", "SAVANNAH": "Savannah",
        "North East Region": "North East", "NORTH EAST": "North East",
        "Oti Region": "Oti", "OTI": "Oti",
        "Western North Region": "Western North", "WESTERN NORTH": "Western North",
    }
    df["region_normalized"] = (
        df["address_stateOrRegion"].map(region_map).fillna(df["address_stateOrRegion"])
    )
    print("  Regions normalized")

    # Save as parquet
    parquet_path = "/tmp/ghana_facilities_clean.parquet"
    df.to_parquet(parquet_path, index=False)
    print(f"  Saved clean parquet ({os.path.getsize(parquet_path) / 1024:.0f} KB)")

    # Upload
    volume_path = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/ghana_facilities_clean.parquet"
    with open(parquet_path, "rb") as f:
        w.files.upload(volume_path, f, overwrite=True)
    print(f"  Uploaded to {volume_path}")
    return volume_path


# ═════════════════════════════════════════════════════════════════════════════
# Step 3: Create Delta table from Parquet
# ═════════════════════════════════════════════════════════════════════════════
def create_delta_table(warehouse_id: str, parquet_path: str):
    banner("Step 3: Creating Delta table from parquet")

    run_sql(warehouse_id, f"DROP TABLE IF EXISTS {TABLE_FQN}",
            "Drop old table (if any)")

    run_sql(warehouse_id, f"""
    CREATE TABLE {TABLE_FQN}
    AS SELECT * FROM read_files('{parquet_path}', format => 'parquet')
    """, "Create table from parquet")

    rows = run_sql(warehouse_id, f"SELECT COUNT(*) FROM {TABLE_FQN}", "Count rows")
    if rows:
        print(f"     {rows[0][0]} rows loaded")

    # Enable Change Data Feed (required for Vector Search sync)
    run_sql(warehouse_id,
            f"ALTER TABLE {TABLE_FQN} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)",
            "Enable Change Data Feed")

    # Verify key distributions
    rows = run_sql(warehouse_id,
                   f"SELECT facilityTypeId, COUNT(*) FROM {TABLE_FQN} WHERE facilityTypeId IS NOT NULL GROUP BY 1 ORDER BY 2 DESC",
                   "Facility type distribution")
    if rows:
        for row in rows:
            print(f"     {row[0]}: {row[1]}")

    print("  Table ready")


# ═════════════════════════════════════════════════════════════════════════════
# Step 4: Add Column Descriptions for Genie
# ═════════════════════════════════════════════════════════════════════════════
def add_column_descriptions(warehouse_id: str):
    banner("Step 4: Adding column descriptions for Genie")

    descriptions = [
        ("name", "Official name of healthcare facility or NGO"),
        ("`procedure`", "JSON array of clinical procedures"),
        ("equipment", "JSON array of medical devices"),
        ("capability", "JSON array of care levels and accreditations"),
        ("specialties", "JSON array of camelCase medical specialties"),
        ("facilityTypeId", "Facility type: hospital clinic dentist pharmacy or doctor"),
        ("address_stateOrRegion", "Ghana region raw"),
        ("region_normalized", "Cleaned Ghana region name one of 16 official regions"),
        ("address_city", "City or town where facility is located"),
        ("description", "Free-form text about the facility - core IDP source"),
        ("unique_id", "UUID primary key for each facility record"),
    ]

    for col, desc in descriptions:
        run_sql(warehouse_id,
                f"ALTER TABLE {TABLE_FQN} ALTER COLUMN {col} COMMENT '{desc}'")

    print("  Column descriptions added")


# ═════════════════════════════════════════════════════════════════════════════
# Step 5: Create Vector Search Endpoint + Index
# ═════════════════════════════════════════════════════════════════════════════
def create_vector_search():
    banner("Step 5: Creating Vector Search endpoint and index")

    from databricks.vector_search.client import VectorSearchClient

    vsc = VectorSearchClient(
        workspace_url=DATABRICKS_HOST,
        personal_access_token=DATABRICKS_TOKEN,
        disable_notice=True,
    )

    # Create endpoint
    try:
        vsc.create_endpoint(name=VS_ENDPOINT, endpoint_type="STANDARD")
        print(f"  Created endpoint: {VS_ENDPOINT}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"  Endpoint '{VS_ENDPOINT}' already exists")
        else:
            print(f"  WARNING: {e}")

    # Wait for endpoint to come online
    print("  Waiting for endpoint to come online...")
    for i in range(60):
        try:
            ep = vsc.get_endpoint(VS_ENDPOINT)
            status = ep.get("endpoint_status", {}).get("state", "UNKNOWN")
            if status == "ONLINE":
                print(f"  Endpoint is ONLINE")
                break
            print(f"    [{i * 10}s] state: {status}")
        except Exception:
            pass
        time.sleep(10)
    else:
        print("  WARNING: Endpoint still not online after 10 min")

    # Create index (single embedding column: description)
    try:
        vsc.create_delta_sync_index(
            endpoint_name=VS_ENDPOINT,
            index_name=VS_INDEX,
            source_table_name=TABLE_FQN,
            pipeline_type="TRIGGERED",
            primary_key="unique_id",
            embedding_source_column="description",
            embedding_model_endpoint_name="databricks-gte-large-en",
            columns_to_sync=[
                "name", "facilityTypeId", "address_city",
                "region_normalized", "specialties", "description",
                "capability", "procedure", "equipment",
            ],
        )
        print(f"  Index created: {VS_INDEX}")
        print("  Index will sync in the background (10-15 min)")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"  Index already exists")
        else:
            print(f"  WARNING: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# Step 6: Update .env
# ═════════════════════════════════════════════════════════════════════════════
def update_env():
    banner("Step 6: Updating .env")

    # Read and rewrite .env cleanly (avoid set_key quoting issues)
    env_vars = {
        "DATABRICKS_HOST": DATABRICKS_HOST,
        "DATABRICKS_TOKEN": DATABRICKS_TOKEN,
        "DATABRICKS_CATALOG": CATALOG,
        "DATABRICKS_SCHEMA": SCHEMA,
        "GENIE_SPACE_ID": os.getenv("GENIE_SPACE_ID", ""),
        "VECTOR_SEARCH_INDEX": VS_INDEX,
        "VECTOR_SEARCH_ENDPOINT": VS_ENDPOINT,
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
    }

    with open(ENV_PATH, "w") as f:
        f.write("# === Databricks (primary backend) ===\n")
        for key in ["DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_CATALOG",
                     "DATABRICKS_SCHEMA", "GENIE_SPACE_ID",
                     "VECTOR_SEARCH_INDEX", "VECTOR_SEARCH_ENDPOINT"]:
            f.write(f"{key}={env_vars[key]}\n")
        f.write("\n# === LLM (fallback if Model Serving quota exceeded) ===\n")
        f.write(f"OPENAI_API_KEY={env_vars['OPENAI_API_KEY']}\n")

    print(f"  Updated {ENV_PATH}:")
    print(f"    DATABRICKS_CATALOG={CATALOG}")
    print(f"    DATABRICKS_SCHEMA={SCHEMA}")
    print(f"    VECTOR_SEARCH_INDEX={VS_INDEX}")
    print(f"    VECTOR_SEARCH_ENDPOINT={VS_ENDPOINT}")


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
def main():
    print("+" + "=" * 58 + "+")
    print("|  Phase 1: Databricks Setup via SDK" + " " * 23 + "|")
    print("|  Host: " + DATABRICKS_HOST[:50].ljust(50) + "|")
    print("+" + "=" * 58 + "+")

    warehouse_id = find_warehouse()
    create_catalog_schema_volume(warehouse_id)
    parquet_path = clean_and_upload()
    create_delta_table(warehouse_id, parquet_path)
    add_column_descriptions(warehouse_id)
    create_vector_search()
    update_env()

    banner("DONE! One manual step remaining")
    print(f"""
  Create a Genie Space in the Databricks UI:

  1. Go to: {DATABRICKS_HOST}/genie
  2. Click "New" -> add table: {TABLE_FQN}
  3. Add these instructions:
     ─────────────────────────────────────────
     This dataset has 987 healthcare facilities and NGOs in Ghana.
     procedure/equipment/capability are JSON arrays of English strings.
     specialties is a JSON array of camelCase strings like "cardiology".
     Use LIKE '%keyword%' to search within JSON columns.
     region_normalized has clean Ghana region names.
     ─────────────────────────────────────────
  4. Copy the Genie Space ID from the URL and add to .env:
     GENIE_SPACE_ID=<paste-id-here>

  Then verify:
     pytest tests/test_config.py tests/test_tools.py -v
    """)


if __name__ == "__main__":
    main()
