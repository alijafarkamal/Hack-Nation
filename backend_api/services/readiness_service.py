"""Startup/readiness checks for critical backend dependencies."""

from __future__ import annotations

from typing import Any

from src.config import GENIE_SPACE_ID, TABLE_FACILITIES, VS_ENDPOINT, VS_INDEX, db_client
from src.tools.genie_tool import query_genie
from src.tools.model_serving_tool import query_llm
from src.tools.vector_search_tool import get_vector_search_status, query_vector_search


def _ok(name: str, detail: str = "ok") -> dict[str, Any]:
    return {"component": name, "ok": True, "detail": detail}


def _fail(name: str, detail: str) -> dict[str, Any]:
    return {"component": name, "ok": False, "detail": detail[:500]}


def check_workspace_auth() -> dict[str, Any]:
    try:
        me = db_client.current_user.me()
        user = getattr(me, "user_name", None) or "unknown"
        return _ok("workspace_auth", f"user={user}")
    except Exception as e:  # noqa: BLE001
        return _fail("workspace_auth", str(e))


def check_warehouse_query() -> dict[str, Any]:
    try:
        warehouses = list(db_client.warehouses.list())
        if not warehouses:
            return _fail("warehouse_query", "no SQL warehouse available")
        wh = warehouses[0].id
        from databricks.sdk.service.sql import Disposition

        resp = db_client.statement_execution.execute_statement(
            warehouse_id=wh,
            statement="SELECT 1 as ok",
            wait_timeout="20s",
            disposition=Disposition.INLINE,
        )
        if resp.status and getattr(resp.status, "error", None):
            return _fail("warehouse_query", str(resp.status.error))
        return _ok("warehouse_query", "SELECT 1 succeeded")
    except Exception as e:  # noqa: BLE001
        return _fail("warehouse_query", str(e))


def check_genie() -> dict[str, Any]:
    if not GENIE_SPACE_ID:
        return _fail("genie_ping", "GENIE_SPACE_ID not configured")
    try:
        r = query_genie("How many facilities are there?")
        text = str(r.get("text") or "")
        if text or r.get("data"):
            return _ok("genie_ping", (text[:120] or "data rows returned"))
        return _fail("genie_ping", "Genie returned empty payload")
    except Exception as e:  # noqa: BLE001
        return _fail("genie_ping", str(e))


def check_vector_search() -> dict[str, Any]:
    if not VS_ENDPOINT or not VS_INDEX:
        return _fail("vector_search_ping", "VECTOR_SEARCH_ENDPOINT/INDEX not configured")
    try:
        _ = query_vector_search("emergency care bihar", num_results=1)
        st = get_vector_search_status()
        if st.get("ok"):
            return _ok("vector_search_ping", f"hits={st.get('hits', 0)}")
        return _fail("vector_search_ping", str(st.get("warning") or st.get("error") or "unknown"))
    except Exception as e:  # noqa: BLE001
        return _fail("vector_search_ping", str(e))


def check_llm() -> dict[str, Any]:
    try:
        out = query_llm("Reply with exactly OK", "ping", max_tokens=10)
        if "OK" in (out or "").upper():
            return _ok("llm_ping", out[:60])
        return _ok("llm_ping", (out or "")[0:60] or "response received")
    except Exception as e:  # noqa: BLE001
        return _fail("llm_ping", str(e))


def readiness_report() -> dict[str, Any]:
    checks = [
        check_workspace_auth(),
        check_warehouse_query(),
        check_genie(),
        check_vector_search(),
        check_llm(),
    ]
    degraded = [c["component"] for c in checks if not c.get("ok")]
    return {
        "ok": len(degraded) == 0,
        "status": "healthy" if not degraded else "degraded",
        "degraded_components": degraded,
        "checks": checks,
    }
