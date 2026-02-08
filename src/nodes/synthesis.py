"""Synthesis node — Intelligent Synthesis (Core Feature #2).

Cross-references structured fields (facilityTypeId, specialties) against
extracted free-form facts to find contradictions, confirm capabilities,
and build a complete citation-backed answer.

For composite (fan-out) queries, synthesis merges results from 2+ agents
that ran in parallel, noting which data sources contributed.

This implements 'Intelligent Synthesis' (Technical Accuracy = 35% of scoring).
"""

import json

import mlflow

from src.state import AgentState
from src.tools.model_serving_tool import query_llm

SYNTHESIS_PROMPT = """You are a medical data synthesis expert for Ghana healthcare facilities.

Your job is to produce a clear, citation-backed answer by CROSS-REFERENCING structured and unstructured data.

CROSS-REFERENCING RULES:
1. Compare structured field (facilityTypeId, specialties) against free-form text (procedure, equipment, capability).
   - Flag if facilityTypeId="clinic" but capabilities describe hospital-level services (trauma, ICU).
   - Flag if specialties list "ophthalmology" but no eye-related procedures or equipment found.
   - Confirm when structured and unstructured data agree (higher confidence answer).
2. Note data completeness: if a facility has procedures but zero equipment, say so explicitly.
3. Every claim MUST cite the specific facility name, field, and value that supports it.
4. When multiple data sources are provided (parallel agents), MERGE their insights:
   - Look for agreements across sources (higher confidence).
   - Flag discrepancies between sources explicitly.
   - Combine geographic + statistical insights when both are present.

OUTPUT FORMAT (Markdown):
### Answer
[Direct answer to the user's question]

### Supporting Evidence
| Facility | Field | Value | Confidence |
|---|---|---|---|
| [name] | [field] | [value] | High/Medium/Low |

### Data Quality Notes
[Any contradictions, gaps, or flags discovered during cross-referencing]
"""


def _format_result_context(state: AgentState) -> str:
    """Build a context string from all available agent results."""
    parts = []

    if state.get("sql_result"):
        sr = state["sql_result"]
        section = f"**SQL/Genie Result:**\n"
        if sr.get("text"):
            section += f"Answer: {sr['text']}\n"
        if sr.get("sql"):
            section += f"SQL: {sr['sql']}\n"
        if sr.get("data"):
            cols = sr.get("columns", [])
            section += f"Columns: {cols}\n"
            for row in sr["data"][:20]:
                section += f"  {row}\n"
        parts.append(section)

    if state.get("search_result"):
        section = "**Vector Search Results:**\n"
        for i, r in enumerate(state["search_result"][:10]):
            if isinstance(r, dict):
                section += (
                    f"{i+1}. {r.get('name', '?')} ({r.get('facilityTypeId', '?')}, "
                    f"{r.get('address_city', '?')})\n"
                    f"   description: {str(r.get('description', ''))[:200]}\n"
                    f"   specialties: {r.get('specialties', '[]')}\n"
                    f"   procedures: {str(r.get('procedure', ''))[:150]}\n"
                    f"   equipment: {str(r.get('equipment', ''))[:150]}\n"
                    f"   capability: {str(r.get('capability', ''))[:150]}\n"
                )
            else:
                section += f"{i+1}. {r}\n"
        parts.append(section)

    if state.get("extraction_result"):
        er = state["extraction_result"]
        section = "**IDP Extraction Results:**\n"
        for i, extraction in enumerate(er.get("extractions", [])[:5]):
            section += f"{i+1}. {extraction[:500]}\n"
        parts.append(section)

    if state.get("anomaly_result"):
        section = f"**Anomaly Detection Results:**\n{state['anomaly_result'][:1000]}\n"
        parts.append(section)

    if state.get("geo_result"):
        gr = state["geo_result"]
        section = "**Geospatial Results:**\n"
        section += f"Message: {gr.get('message', 'N/A')}\n"
        if gr.get("desert_regions"):
            section += f"Desert regions: {gr['desert_regions']}\n"
        if gr.get("covered_regions"):
            section += f"Covered regions: {gr['covered_regions']}\n"
        if gr.get("facilities"):
            section += "Nearby facilities:\n"
            for f in gr["facilities"][:10]:
                section += f"  - {f.get('name')} ({f.get('distance_km')}km)\n"
        if gr.get("region_counts"):
            section += "Region counts:\n"
            for region, cnt in list(gr["region_counts"].items())[:15]:
                section += f"  - {region}: {cnt}\n"
        parts.append(section)

    return "\n---\n".join(parts) if parts else "No results found from any agent."


# Map result keys to human-readable agent names
_AGENT_LABELS = {
    "sql_result": "SQL/Genie",
    "search_result": "Vector Search",
    "extraction_result": "IDP Extraction",
    "anomaly_result": "Anomaly Detection",
    "geo_result": "Geospatial",
}


def _active_agents(state: AgentState) -> list[str]:
    """Return labels of agents that produced results (for citation trail)."""
    return [
        label
        for key, label in _AGENT_LABELS.items()
        if state.get(key)
    ]


@mlflow.trace(name="synthesis_node", span_type="CHAIN")
def synthesis_node(state: AgentState) -> dict:
    """Synthesis node — cross-references all agent outputs and produces
    a citation-backed answer with data quality flags.

    For fan-out queries, merges parallel results from multiple agents.
    """
    context = _format_result_context(state)
    user_query = state["query"]
    agents_used = _active_agents(state)

    prompt_input = f"User question: {user_query}\n\nAgent results:\n{context}"
    answer = query_llm(SYNTHESIS_PROMPT, prompt_input, max_tokens=2048)

    # Append source attribution for fan-out transparency
    if len(agents_used) > 1:
        answer += (
            f"\n\n**Note:** This answer merges results from {len(agents_used)} "
            f"parallel agents: {', '.join(agents_used)}.\n"
        )

    return {
        "final_answer": answer,
        "citations": [
            {"node": "synthesis", "agents_merged": agents_used}
        ],
    }
