"""Lakebase persistence for Data Readiness Desk (Human Corrections)."""

from __future__ import annotations

import os
import uuid
from typing import Any

from dotenv import load_dotenv

from backend_api.schemas import CorrectionSubmitRequest
from backend_api.services.shortlist_service import _connection

load_dotenv()

CATALOG = os.getenv("DATABRICKS_CATALOG", "hack_nation")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "india_medical")
TABLE = f"{CATALOG}.{SCHEMA}.facility_corrections"

def ensure_table() -> None:
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
      correction_id STRING NOT NULL,
      facility_id STRING NOT NULL,
      facility_name STRING NOT NULL,
      correction_text STRING NOT NULL,
      evidence_link STRING,
      submitted_by STRING,
      status STRING,
      created_at TIMESTAMP
    ) USING DELTA
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(ddl)

def submit_correction(body: CorrectionSubmitRequest) -> dict[str, Any]:
    ensure_table()
    correction_id = str(uuid.uuid4())
    
    insert_sql = f"""
    INSERT INTO {TABLE} (
        correction_id, facility_id, facility_name, correction_text, 
        evidence_link, submitted_by, status, created_at
    ) VALUES (
        :correction_id, :facility_id, :facility_name, :correction_text,
        :evidence_link, :submitted_by, 'PENDING_REVIEW', current_timestamp()
    )
    """
    params = {
        "correction_id": correction_id,
        "facility_id": body.facility_id,
        "facility_name": body.facility_name,
        "correction_text": body.correction_text,
        "evidence_link": body.evidence_link,
        "submitted_by": body.submitted_by
    }
    
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(insert_sql, params)
        
    return {
        "success": True, 
        "correction_id": correction_id, 
        "message": "Correction submitted for human review."
    }
