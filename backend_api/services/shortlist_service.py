"""Persistent referral shortlist backed by a Unity Catalog Delta table."""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from dotenv import load_dotenv

from backend_api.schemas import ShortlistSaveRequest, ShortlistUpdateRequest

load_dotenv()

CATALOG = os.getenv("DATABRICKS_CATALOG", "hack_nation")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "india_medical")
TABLE = os.getenv("SHORTLIST_TABLE", f"{CATALOG}.{SCHEMA}.user_shortlists")


def _hostname() -> str:
    return (os.getenv("DATABRICKS_HOST") or "").removeprefix("https://").rstrip("/")


@contextmanager
def _connection() -> Iterator[Any]:
    """Connect lazily so a warehouse outage never blocks FastAPI startup."""
    from databricks import sql

    host = _hostname()
    token = (os.getenv("DATABRICKS_TOKEN") or "").strip()
    http_path = (os.getenv("DATABRICKS_SQL_HTTP_PATH") or "").strip()
    if not (host and token and http_path):
        raise RuntimeError(
            "Shortlist persistence requires DATABRICKS_HOST, DATABRICKS_TOKEN, "
            "and DATABRICKS_SQL_HTTP_PATH."
        )
    with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
        yield conn


def ensure_table() -> None:
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
      shortlist_id STRING NOT NULL,
      session_id STRING NOT NULL,
      facility_id STRING NOT NULL,
      facility_name STRING NOT NULL,
      user_notes STRING,
      system_trust_score DOUBLE,
      system_verdict STRING,
      trust_override DOUBLE,
      override_reason STRING,
      evidence_json STRING,
      facility_snapshot_json STRING,
      watchlist_status STRING,
      watchlist_reason STRING,
      created_at TIMESTAMP,
      updated_at TIMESTAMP
    ) USING DELTA
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(ddl)


def save(body: ShortlistSaveRequest) -> dict[str, Any]:
    ensure_table()
    shortlist_id = str(uuid.uuid4())
    merge = f"""
    MERGE INTO {TABLE} AS target
    USING (SELECT :session_id AS session_id, :facility_id AS facility_id) AS source
    ON target.session_id = source.session_id AND target.facility_id = source.facility_id
    WHEN MATCHED THEN UPDATE SET
      facility_name=:facility_name, user_notes=:user_notes,
      system_trust_score=:system_trust_score, system_verdict=:system_verdict,
      evidence_json=:evidence_json, facility_snapshot_json=:snapshot_json,
      updated_at=current_timestamp()
    WHEN NOT MATCHED THEN INSERT (
      shortlist_id, session_id, facility_id, facility_name, user_notes,
      system_trust_score, system_verdict, trust_override, override_reason,
      evidence_json, facility_snapshot_json, watchlist_status, watchlist_reason,
      created_at, updated_at
    ) VALUES (
      :shortlist_id, :session_id, :facility_id, :facility_name, :user_notes,
      :system_trust_score, :system_verdict, NULL, '', :evidence_json,
      :snapshot_json, 'CLEAR', '', current_timestamp(), current_timestamp()
    )
    """
    params = {
        "shortlist_id": shortlist_id,
        "session_id": body.session_id,
        "facility_id": body.facility_id,
        "facility_name": body.facility_name,
        "user_notes": body.user_notes,
        "system_trust_score": body.system_trust_score,
        "system_verdict": body.system_verdict,
        "evidence_json": json.dumps(body.evidence, default=str),
        "snapshot_json": json.dumps(body.facility_snapshot, default=str),
    }
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(merge, params)
    return {"success": True, "shortlist_id": shortlist_id, "session_id": body.session_id}


def list_for_session(session_id: str) -> list[dict[str, Any]]:
    ensure_table()
    query = f"""
    SELECT shortlist_id, session_id, facility_id, facility_name, user_notes,
      system_trust_score, system_verdict, trust_override, override_reason,
      evidence_json, facility_snapshot_json, watchlist_status, watchlist_reason,
      created_at, updated_at
    FROM {TABLE} WHERE session_id=:session_id ORDER BY updated_at DESC
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(query, {"session_id": session_id})
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, row)) for row in cur.fetchall()]
    for row in rows:
        row["evidence"] = json.loads(row.pop("evidence_json") or "[]")
        row["facility_snapshot"] = json.loads(row.pop("facility_snapshot_json") or "{}")
        row["effective_trust_score"] = (
            row["trust_override"] if row["trust_override"] is not None else row["system_trust_score"]
        )
    return rows


def update(body: ShortlistUpdateRequest) -> dict[str, Any]:
    ensure_table()
    statement = f"""
    UPDATE {TABLE} SET user_notes=:user_notes, trust_override=:trust_override,
      override_reason=:override_reason, updated_at=current_timestamp()
    WHERE session_id=:session_id AND facility_id=:facility_id
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(statement, body.model_dump())
    return {"success": True, "session_id": body.session_id, "facility_id": body.facility_id}


def remove(session_id: str, facility_id: str) -> dict[str, Any]:
    ensure_table()
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM {TABLE} WHERE session_id=:session_id AND facility_id=:facility_id",
            {"session_id": session_id, "facility_id": facility_id},
        )
    return {"success": True}


def refresh_watchlist(session_id: str) -> dict[str, Any]:
    """Flag saved facilities whose latest dataset trust is materially worse."""
    ensure_table()
    facilities = f"{CATALOG}.{SCHEMA}.india_facilities"
    statement = f"""
    MERGE INTO {TABLE} AS saved
    USING (
      SELECT name, MAX(CASE WHEN trust_score > 1 THEN trust_score / 100 ELSE trust_score END) AS latest_score,
        MAX(lower(coalesce(trust_flag, ''))) AS latest_flag
      FROM {facilities} GROUP BY name
    ) AS latest
    ON saved.facility_name = latest.name AND saved.session_id=:session_id
    WHEN MATCHED THEN UPDATE SET
      watchlist_status = CASE
        WHEN latest.latest_flag IN ('suspicious','low','review')
          OR latest.latest_score < coalesce(saved.system_trust_score, 0.5) - 0.15
        THEN 'ALERT' ELSE 'CLEAR' END,
      watchlist_reason = CASE
        WHEN latest.latest_flag IN ('suspicious','low','review') THEN concat('Latest dataset flag: ', latest.latest_flag)
        WHEN latest.latest_score < coalesce(saved.system_trust_score, 0.5) - 0.15 THEN 'Latest trust score dropped by more than 15 points'
        ELSE '' END,
      updated_at=current_timestamp()
    """
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(statement, {"session_id": session_id})
    return {"success": True, "session_id": session_id, "items": list_for_session(session_id)}
