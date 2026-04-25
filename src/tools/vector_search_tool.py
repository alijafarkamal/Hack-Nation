"""Mosaic AI Vector Search — semantic retrieval over India facility text."""

import logging

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


@mlflow.trace(name="query_vector_search", span_type="RETRIEVER")
def query_vector_search(
    query_text: str,
    num_results: int = 10,
    filters: dict | None = None,
) -> list[dict]:
    if vs_client is None or not VS_ENDPOINT or not VS_INDEX:
        logger.warning("Vector Search not configured — returning empty results")
        return []

    try:
        index = vs_client.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
    except Exception as e:
        logger.warning("Vector Search get_index failed: %s", e)
        return []

    kwargs: dict = dict(
        query_text=query_text,
        columns=_COLUMNS,
        num_results=num_results,
    )
    if filters:
        kwargs["filters"] = filters

    try:
        raw = index.similarity_search(**kwargs)
    except Exception as e:
        logger.warning("Vector Search similarity_search failed: %s", e)
        return []

    data_array = raw.get("result", {}).get("data_array", [])
    col_names = [c["name"] for c in raw.get("manifest", {}).get("columns", [])]
    return [dict(zip(col_names, row)) for row in data_array]
