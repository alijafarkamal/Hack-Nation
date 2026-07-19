"""Mosaic AI Vector Search — semantic retrieval over India facility text."""

import logging
import re
from typing import Any

import mlflow

from src.config import VS_ENDPOINT, VS_INDEX, vs_client

logger = logging.getLogger(__name__)

_COLUMNS = [
    "name",
    "facilityTypeId",
    "address_city",
    "state_normalized",
    "pin_code",
    "specialties",
    "description",
    "capability",
    "procedure",
    "equipment",
    "trust_score",
    "trust_flag",
    "latitude",
    "longitude",
]

_LAST_STATUS: dict[str, Any] = {
    "ok": True,
    "configured": True,
    "hits": 0,
    "degraded_components": [],
    "warning": None,
    "error": None,
}


def get_vector_search_status() -> dict[str, Any]:
    """Return status from the latest vector-search call."""
    return dict(_LAST_STATUS)


def _set_status(**kwargs: Any) -> None:
    _LAST_STATUS.update(kwargs)


@mlflow.trace(name="query_vector_search", span_type="RETRIEVER")
def query_vector_search(
    query_text: str,
    num_results: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    if vs_client is None or not VS_ENDPOINT or not VS_INDEX:
        msg = "Vector Search not configured"
        logger.warning("%s — returning empty results", msg)
        _set_status(
            ok=False,
            configured=False,
            hits=0,
            degraded_components=["vector_search"],
            warning=msg,
            error=msg,
        )
        return []

    try:
        index = vs_client.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
    except Exception as e:
        msg = f"Vector Search get_index failed: {e}"
        logger.warning(msg)
        _set_status(
            ok=False,
            configured=True,
            hits=0,
            degraded_components=["vector_search"],
            warning="Vector search unavailable; falling back to non-vector paths",
            error=str(e),
        )
        return []

    kwargs: dict = dict(
        query_text=query_text,
        columns=_COLUMNS,
        num_results=num_results,
        disable_notice=True,
    )
    if filters:
        kwargs["filters"] = filters

    try:
        raw = index.similarity_search(**kwargs)
    except Exception as e:
        # Common runtime issue: index schema changed and one requested column is missing.
        err = str(e)
        m = re.search(r"Requested columns to fetch are not present in index:\s*(.+)$", err)
        if m:
            missing_cols = [c.strip() for c in m.group(1).split(",") if c.strip()]
            retry_cols = [c for c in _COLUMNS if c not in set(missing_cols)]
            if retry_cols:
                try:
                    raw = index.similarity_search(
                        query_text=query_text,
                        columns=retry_cols,
                        num_results=num_results,
                        disable_notice=True,
                        **({"filters": filters} if filters else {}),
                    )
                    data_array = raw.get("result", {}).get("data_array", [])
                    col_names = [c["name"] for c in raw.get("manifest", {}).get("columns", [])]
                    out = [dict(zip(col_names, row)) for row in data_array]
                    _set_status(
                        ok=True,
                        configured=True,
                        hits=len(out),
                        degraded_components=["vector_search"] if missing_cols else [],
                        warning=(
                            f"Vector search schema drift: pruned columns {missing_cols}; "
                            "results may contain fewer fields"
                        ),
                        error=None,
                    )
                    return out
                except Exception as e2:
                    err = str(e2)
        msg = f"Vector Search similarity_search failed: {err}"
        logger.warning(msg)
        _set_status(
            ok=False,
            configured=True,
            hits=0,
            degraded_components=["vector_search"],
            warning="Vector search query failed; returning empty results",
            error=err,
        )
        return []

    data_array = raw.get("result", {}).get("data_array", [])
    col_names = [c["name"] for c in raw.get("manifest", {}).get("columns", [])]
    out = [dict(zip(col_names, row)) for row in data_array]
    _set_status(
        ok=True,
        configured=True,
        hits=len(out),
        degraded_components=[],
        warning=None,
        error=None,
    )
    return out
