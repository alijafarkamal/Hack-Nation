"""Databricks Mosaic AI Vector Search SDK wrapper — RAG.

Performs semantic search over the procedure/equipment/capability columns
of the Ghana facilities Delta table using auto-generated embeddings.

Ref: https://docs.databricks.com/en/generative-ai/vector-search
"""

from src.config import db_client, VS_INDEX


def query_vector_search(
    query_text: str,
    num_results: int = 10,
    filters: dict | None = None,
) -> list:
    """Semantic search over facility free-form text columns.

    Args:
        query_text: Natural language query for semantic matching.
        num_results: Number of top-k results to return.
        filters: Optional column filters (e.g., {"facilityTypeId": "hospital"}).

    Returns:
        List of matching facility records (each is a list of column values).
    """
    results = db_client.vector_search_indexes.query_index(
        index_name=VS_INDEX,
        columns=[
            "name",
            "procedure",
            "equipment",
            "capability",
            "address_city",
            "facilityTypeId",
            "specialties",
        ],
        query_text=query_text,
        num_results=num_results,
        filters=filters,
    )
    return results.data_array
