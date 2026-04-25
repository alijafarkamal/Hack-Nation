"""SQL agent: Genie Text-to-SQL on `india_facilities` with aggregate → detail rewrite."""

import logging
import os
import re

import mlflow

from src.config import TABLE_FACILITIES, db_client
from src.data_loader import CITY_TO_STATE
from src.state import AgentState
from src.tools.genie_tool import query_genie
from src.utils.confidence import completeness_penalty, ratio_dict

log = logging.getLogger(__name__)

_DETAIL_COLS = f"name, state_normalized, facilityTypeId, address_city"


def _fill_state(row: list[str]) -> list[str]:
    """Fill missing `state_normalized` (index 1) when empty."""
    st = (row[1] or "").strip() if len(row) > 1 else ""
    if st and st.lower() not in ("", "unknown", "none", "null"):
        return row
    city = (row[3] or "").strip() if len(row) > 3 else ""
    if city and city in CITY_TO_STATE:
        row[1] = CITY_TO_STATE[city]
        return row
    row[1] = "Unknown"
    return row


def _is_aggregate_only(result: dict) -> bool:
    data = result.get("data", [])
    cols = [c.lower() for c in result.get("columns", [])]
    if len(data) <= 1 and len(cols) <= 2:
        count_keywords = {"count", "cnt", "total", "sum", "avg", "min", "max"}
        if any(kw in c for c in cols for kw in count_keywords):
            return True
        if len(data) == 1 and len(data[0]) == 1:
            try:
                int(data[0][0])
                return True
            except (ValueError, TypeError):
                pass
    return False


def _rewrite_count_to_select(sql: str) -> str | None:
    if not sql:
        return None
    pattern = re.compile(
        r"SELECT\s+COUNT\s*\([^)]*\).*?FROM",
        re.IGNORECASE | re.DOTALL,
    )
    if not pattern.search(sql):
        return None
    rewritten = pattern.sub(f"SELECT {_DETAIL_COLS} FROM", sql, count=1)
    rewritten = re.sub(r"\bORDER\s+BY\s+.*$", "", rewritten, flags=re.IGNORECASE)
    if "LIMIT" not in rewritten.upper():
        rewritten = rewritten.rstrip().rstrip(";") + " LIMIT 30"
    return rewritten


def _run_sql_direct(sql: str) -> tuple[list[list[str]], list[str]]:
    catalog = os.getenv("DATABRICKS_CATALOG", "hack_nation")
    schema = os.getenv("DATABRICKS_SCHEMA", "india_medical")
    warehouses = list(db_client.warehouses.list())
    if not warehouses:
        return [], []
    wh_id = warehouses[0].id
    resp = db_client.statement_execution.execute_statement(
        warehouse_id=wh_id,
        statement=sql,
        catalog=catalog,
        schema=schema,
    )
    rows: list = []
    columns: list = []
    if resp.result and resp.result.data_array:
        rows = resp.result.data_array
    if resp.manifest and resp.manifest.schema:
        columns = [c.name for c in resp.manifest.schema.columns]
    return rows, columns


@mlflow.trace(name="sql_agent_node", span_type="AGENT")
def sql_agent_node(state: AgentState) -> dict:
    result = query_genie(state["query"])

    if _is_aggregate_only(result):
        log.info("Aggregate-only — rewriting SQL for facility details")
        original_sql = result.get("sql", "")
        detail_sql = _rewrite_count_to_select(original_sql)
        if detail_sql:
            try:
                rows, cols = _run_sql_direct(detail_sql)
                if rows:
                    seen: set[str] = set()
                    unique_rows: list[list[str]] = []
                    for r in rows:
                        key = r[0] if r else ""
                        if key and key not in seen:
                            seen.add(key)
                            unique_rows.append(r)
                    unique_rows = [_fill_state(list(x)) for x in unique_rows]
                    result["detail_data"] = unique_rows
                    result["detail_columns"] = cols
            except Exception as e:
                log.warning("Direct SQL failed: %s", e)
        if not result.get("detail_data"):
            try:
                detail_query = (
                    f"List the names, states (state_normalized), and facility types "
                    f"from {TABLE_FACILITIES} for: {state['query']}"
                )
                dr = query_genie(detail_query)
                if dr.get("data"):
                    result["detail_data"] = dr["data"]
                    result["detail_columns"] = dr.get("columns", [])
            except Exception as e:
                log.warning("Genie follow-up failed: %s", e)

    # Confidence / completeness for downstream synthesis (Challenge confidence stretch)
    detail_data = result.get("detail_data") or []
    detail_cols = [str(c).lower() for c in (result.get("detail_columns") or [])]
    k_high, n = 0, len(detail_data)
    if n and "trust_score" in detail_cols:
        ti = detail_cols.index("trust_score")
        for r in detail_data:
            if ti >= len(r):
                continue
            try:
                v = r[ti]
                if v is None or v == "":
                    continue
                fv = float(v)
                if fv > 1.0:
                    fv /= 100.0
                if fv >= 0.65:
                    k_high += 1
            except (TypeError, ValueError, IndexError):
                continue
    if n and k_high >= 0:
        result["sql_high_trust_interval"] = ratio_dict(
            k_high,
            n,
            has_equipment=bool("equipment" in str(result.get("text", "")).lower() or n > 0),
            has_procedure=True,
            has_capacity=True,
        )
    else:
        result["sql_high_trust_interval"] = None
    first_row: dict = {}
    if detail_data and result.get("detail_columns"):
        cc = [str(c) for c in (result.get("detail_columns") or [])]
        row0 = detail_data[0] if detail_data[0] else []
        for i, k in enumerate(cc):
            if i < len(row0):
                first_row[k] = row0[i]
    desc_len = len(str(result.get("text", "") or ""))
    result["completeness_penalty"] = completeness_penalty(
        has_equipment="equipment" in str(first_row).lower() or "equipment" in str(result.get("sql", "")).lower(),
        has_procedure="procedure" in str(first_row).lower() or "procedure" in str(result.get("sql", "")).lower(),
        has_capacity="capability" in str(first_row).lower(),
        description_len=desc_len,
    )
    return {
        "sql_result": result,
        "citations": [
            {
                "source": "genie",
                "field": "sql",
                "sql": result.get("sql"),
                "description": result.get("description"),
            }
        ],
    }
