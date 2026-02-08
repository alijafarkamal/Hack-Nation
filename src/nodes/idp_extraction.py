"""IDP Extraction node — Core Feature #1 (IDP Innovation = 30% of scoring).

Retrieves facility free-form text via Vector Search, then uses the LLM to
extract structured facts (procedures, equipment, capabilities, inferred
specialties, confidence flags) from unstructured text.

This is the heart of the challenge — going beyond keyword search to
structured fact extraction using the sponsor's prompt patterns.

Ref: resources/prompts_and_pydantic_models/free_form.py
"""

import json

import mlflow

from src.state import AgentState
from src.tools.model_serving_tool import query_llm
from src.tools.vector_search_tool import query_vector_search

IDP_EXTRACTION_PROMPT = """You are a specialized medical facility information extractor.

Given a facility's raw free-form text data (procedure, equipment, capability arrays),
extract and return STRUCTURED facts in this JSON format:

{
  "facility_name": "...",
  "parsed_procedures": ["Performs emergency cesarean sections", ...],
  "parsed_equipment": ["Has Siemens CT scanner", ...],
  "parsed_capabilities": ["Level II trauma center", "24/7 emergency care", ...],
  "inferred_specialties": ["generalSurgery", "emergencyMedicine", ...],
  "facility_level": "hospital|clinic|specialist_center",
  "confidence_flags": ["procedure X claimed but no supporting equipment listed", ...]
}

RULES:
- Extract ONLY facts directly stated in the data. Do not infer from general knowledge.
- Map capabilities to standard specialty names (camelCase): cardiology, ophthalmology, etc.
- Flag any contradictions between procedure claims and equipment lists.
- Each fact must be a clear, declarative English statement.
- Empty arrays [] mean "no data found" — this is a valid signal, not missing data."""


@mlflow.trace(name="idp_extraction_node", span_type="AGENT")
def idp_extraction_node(state: AgentState) -> dict:
    """IDP Extraction — retrieves free-form text via Vector Search, then
    uses the LLM to extract structured facts from unstructured procedure/
    equipment/capability arrays.

    This is the core IDP innovation the challenge evaluates (30% of score).
    """
    # Step 1: Retrieve relevant facilities via semantic search
    raw_facilities = query_vector_search(state["query"], num_results=5)

    # Step 2: For each facility, extract structured facts via LLM
    extractions = []
    for facility in raw_facilities:
        extraction = query_llm(IDP_EXTRACTION_PROMPT, json.dumps(facility))
        extractions.append(extraction)

    return {
        "extraction_result": {
            "query": state["query"],
            "extractions": extractions,
        },
        "citations": state["citations"]
        + [{"source": "idp_extraction", "facilities_processed": len(raw_facilities)}],
    }
