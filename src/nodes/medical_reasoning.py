"""Medical Reasoning node — anomaly detection via Model Serving.

Cross-references a facility's claimed procedures, equipment, and capabilities
to detect mismatches, inflated claims, and missing basics.

Ref: https://docs.databricks.com/en/machine-learning/model-serving
"""

from src.state import AgentState
from src.tools.model_serving_tool import query_llm
from src.tools.vector_search_tool import query_vector_search

MEDICAL_REASONING_PROMPT = """You are a medical facility verification expert for Ghana.

You detect anomalies by cross-referencing a facility's claimed procedures, equipment, and capabilities.

PROCEDURE-EQUIPMENT DEPENDENCIES (flag if procedure claimed without required equipment):
- Cataract surgery → requires: operating microscope, phacoemulsification unit
- MRI diagnostics → requires: MRI scanner
- CT scan → requires: CT scanner
- Hemodialysis → requires: dialysis machines
- Cesarean section → requires: operating theater, anesthesia equipment
- Laparoscopic surgery → requires: laparoscope, insufflator
- X-ray → requires: X-ray machine
- Ultrasound → requires: ultrasound machine
- ICU care → requires: ventilators, cardiac monitors

ANOMALY PATTERNS:
1. PROCEDURE-EQUIPMENT GAP: Claims surgical procedures but lists zero surgical equipment
2. SPECIALTY-PROCEDURE MISMATCH: Lists specialty but no related procedures
3. BREADTH WITHOUT DEPTH: Many specialties (>5) but zero procedures and zero equipment
4. CAPABILITY INFLATION: Broad claims ("world-class") with no supporting data
5. MISSING BASICS: Hospital type but no emergency or inpatient capability

For each facility, return:
- VERDICT: CLEAN, WARNING, or FLAG
- REASON: Specific explanation
- EVIDENCE: Which data fields support your conclusion
- FACILITY: Name and city"""


def medical_reasoning_node(state: AgentState) -> dict:
    """Medical Reasoning — retrieves facilities via Vector Search, then
    uses the LLM to detect anomalies by cross-referencing procedures,
    equipment, and capabilities."""
    # Get facilities relevant to the anomaly query
    facilities = query_vector_search(state["query"], num_results=20)
    analysis = query_llm(MEDICAL_REASONING_PROMPT, str(facilities))
    return {
        "anomaly_result": analysis,
        "citations": state["citations"]
        + [{"source": "medical_reasoning", "facilities_analyzed": len(facilities)}],
    }
