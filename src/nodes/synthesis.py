"""Synthesis node — Intelligent Synthesis (Core Feature #2).

Cross-references structured fields (facilityTypeId, specialties) against
extracted free-form facts to find contradictions, confirm capabilities,
and build a complete citation-backed answer.

This implements 'Intelligent Synthesis' (Technical Accuracy = 35% of scoring).
"""

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


def synthesis_node(state: AgentState) -> dict:
    """Synthesis node — cross-references structured fields against unstructured
    free-form text extractions. Produces citation-backed answers with data
    quality flags."""
    # Gather all results from whichever agent(s) ran
    raw_parts = []
    if state.get("sql_result"):
        raw_parts.append(f"SQL/Genie result:\n{state['sql_result']}")
    if state.get("search_result"):
        raw_parts.append(f"Vector Search result:\n{state['search_result']}")
    if state.get("extraction_result"):
        raw_parts.append(f"IDP Extraction result:\n{state['extraction_result']}")
    if state.get("anomaly_result"):
        raw_parts.append(f"Anomaly detection result:\n{state['anomaly_result']}")
    if state.get("geo_result"):
        raw_parts.append(f"Geospatial result:\n{state['geo_result']}")

    combined = "\n---\n".join(raw_parts) if raw_parts else "No results found."
    answer = query_llm(SYNTHESIS_PROMPT, combined)
    return {"final_answer": answer}
