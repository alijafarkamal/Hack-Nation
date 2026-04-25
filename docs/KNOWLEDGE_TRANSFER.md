# KNOWLEDGE_TRANSFER.md
## Hack Nation Global AI Hackathon — Databricks Track: Winning Architecture

> **Purpose:** This document is the primary context file for the next Databricks-track hackathon project. It extracts every architectural decision, code pattern, prompt template, data pattern, and lesson from the winning Medical-Intelligence-Agent submission. The next project's Cursor agent should read this before writing a single line of code.

---

## 1. WINNING ARCHITECTURE OVERVIEW

### High-Level System Design

The system is a **multi-agent intelligence platform** built on LangGraph for local orchestration, with Databricks Free Edition as the cloud intelligence backend. The key insight: **all heavy intelligence runs on Databricks** (SQL, semantic search, LLM inference), while **all deterministic logic runs locally** (geospatial math, rendering, fallbacks).

The architecture has three clear layers:
1. **Frontend** — Streamlit with three tabs: Agent Chat, Mission Planner, Interactive Map
2. **Agent Graph** — LangGraph StateGraph with supervisor-routed specialized nodes, all running locally
3. **Databricks Backend** — Unity Catalog (Delta), Genie (Text-to-SQL), Vector Search (RAG), Model Serving (LLM)

### Orchestration Pattern: Supervisor + Conditional Fan-Out

The pattern is: **supervisor node → conditional routing → 1–2 specialized agent nodes (in parallel for composite queries) → synthesis node → END**.

This is NOT a simple linear pipeline. The supervisor can fan-out to 2 agents simultaneously for composite queries (e.g., "hospitals near Tamale with cardiology deserts" → GEO + SQL in parallel). The synthesis node always merges all results.

The supervisor does **two LLM calls** before routing:
1. **Normalize** the query (fix typos/grammar for cleaner Genie SQL generation)
2. **Classify** into 1 or 2 intent labels (supports composite queries natively)

### Data Flow: Raw Input to Final Output

```
User types question in Streamlit
  ↓
LangGraph graph.invoke({"query": query, "citations": []})
  ↓
supervisor_node:
  Step 1 → LLM: normalize query (fix typos, improve grammar)
  Step 2 → LLM: classify into SQL | SEARCH | EXTRACT | ANOMALY | GEO (or 2 of these)
  Returns: {"query": cleaned_query, "intents": ["SQL"] or ["GEO", "SQL"]}
  ↓
Conditional fan-out (route_by_intents returns a list → LangGraph parallelizes)
  ↓
One or two of these nodes run (in parallel if 2 intents):
  ┌─ sql_agent_node → query_genie() → Databricks Genie → Delta table
  ├─ rag_agent_node → query_vector_search() → Databricks Vector Search
  ├─ idp_extraction_node → query_vector_search() + query_llm() → structured JSON facts
  ├─ medical_reasoning_node → query_vector_search() + query_llm() → anomaly verdicts
  └─ geospatial_node → direct SQL + local Haversine math
  ↓
synthesis_node:
  Formats all agent results into context string
  LLM call with SYNTHESIS_PROMPT
  Returns: citation-backed markdown answer
  ↓
run_agent() returns final_answer string
  ↓
Streamlit renders markdown answer
MLflow traces every step (span_type: AGENT / TOOL / RETRIEVER / LLM / CHAIN)
```

### ASCII Agent Graph Topology

```
                        ┌─────────────────────────────────────────┐
                        │         Streamlit Frontend               │
                        │  [Chat Tab] [Mission Planner] [Map Tab]  │
                        └───────────────┬─────────────────────────┘
                                        │ query
                                        ▼
                             ┌──────────────────┐
                             │  supervisor_node  │
                             │  1. Normalize     │
                             │  2. Classify      │
                             └────────┬─────────┘
                                      │ intents: list[str]
              ┌───────────────────────┼───────────────────────┐
              │  route_by_intents()   │  (returns list →       │
              │  (conditional edges)  │   LangGraph fan-out)   │
              ▼           ▼           ▼           ▼           ▼
           ┌─────┐    ┌──────┐   ┌────────┐  ┌────────┐  ┌─────┐
           │ SQL │    │SEARCH│   │EXTRACT │  │ANOMALY │  │ GEO │
           │     │    │      │   │        │  │        │  │     │
           │Genie│    │VecSrch   │VS+LLM  │  │VS+LLM  │  │SQL+ │
           └──┬──┘    └──┬───┘   └───┬────┘  └───┬────┘  │Havr │
              │          │           │            │       └──┬──┘
              └──────────┴───────────┴────────────┴──────────┘
                                      │ (all edges → synthesis)
                                      ▼
                             ┌─────────────────┐
                             │ synthesis_node   │
                             │ Cross-reference  │
                             │ structured vs    │
                             │ unstructured     │
                             │ Citation table   │
                             └────────┬─────────┘
                                      │ final_answer (markdown)
                                      ▼
                             ┌─────────────────┐
                             │      END         │
                             └─────────────────┘

Databricks Backend (remote, called via SDK from each node):
  ┌────────────┐  ┌──────────────────┐  ┌───────────────┐  ┌─────────┐
  │Unity Catalog│  │Genie Text-to-SQL │  │Vector Search  │  │Model    │
  │Delta Table  │  │(natural lang→SQL)│  │(gte-large-en) │  │Serving  │
  └────────────┘  └──────────────────┘  └───────────────┘  │Qwen3 80B│
                                                             └─────────┘
MLflow: @mlflow.trace on every node + tool (span_type annotations)
```

---

## 2. TECH STACK & DEPENDENCIES

### Exact requirements.txt (pinned versions)

```
# Agent orchestration
langgraph==1.0.8
langchain==1.2.9
langchain-openai==1.1.7

# Databricks SDK
databricks-sdk==0.85.0
databricks-vectorsearch==0.64
mlflow==3.9.0

# Frontend
streamlit==1.54.0
streamlit-folium==0.26.1
folium==0.20.0

# Data (local utilities)
pandas==2.3.3
numpy==2.4.2
python-dotenv==1.2.1

# Charts (dashboard)
plotly>=5.18.0

# PDF export (planning report)
fpdf2>=2.8.0

# Testing
pytest==9.0.2
```

### Why Each Library Was Chosen

| Library | Why Chosen | Critical or Nice-to-Have |
|---|---|---|
| `langgraph==1.0.8` | State graph with conditional fan-out edges; makes multi-agent routing explainable to judges; supports `Annotated[list, operator.add]` reducer for parallel node citations | **Critical** |
| `databricks-sdk==0.85.0` | Single SDK for Genie, Model Serving, SQL Warehouse, Unity Catalog; replaces fragile REST calls | **Critical** |
| `databricks-vectorsearch==0.64` | Separate SDK for Vector Search index queries (`VectorSearchClient`); not in core SDK | **Critical** |
| `mlflow==3.9.0` | `@mlflow.trace` decorator gives step-level citation trail; judges explicitly asked for this; `mlflow.set_tracking_uri("databricks")` points to workspace | **Critical** |
| `streamlit==1.54.0` | Fastest UI for hackathon; 3-tab layout (Chat, Planner, Map) in ~100 lines | **Critical** |
| `folium==0.20.0` + `streamlit-folium==0.26.1` | Interactive map with color-coded markers and desert overlays; judge-visible social impact | **Critical** |
| `pandas==2.3.3` | CSV cleaning, data loading, local fallback when Databricks unavailable | **Critical** |
| `python-dotenv==1.2.1` | Load `.env` for all credentials; `load_dotenv()` at top of `config.py` | **Critical** |
| `plotly>=5.18.0` | Bar/pie charts in Mission Planner tab | Nice-to-have |
| `fpdf2>=2.8.0` | PDF export button in Mission Planner | Nice-to-have |
| `langchain==1.2.9` | Required by langgraph; provides `ChatMessage` types | Indirect |
| `langchain-openai==1.1.7` | OpenAI-compatible client for fallback routing | Nice-to-have |
| `numpy==2.4.2` | Geospatial math support | Nice-to-have |

### Databricks-Specific Integrations

**Genie (Text-to-SQL)** — Most important for structured data questions:
- Initialize with `WorkspaceClient(host=..., token=...)`
- Call: `db_client.genie.start_conversation(space_id=GENIE_SPACE_ID, content=question)`
- Poll: `db_client.genie.get_message(space_id, conversation_id, message_id)`
- Wait for `MessageStatus.COMPLETED`
- Extract results: `db_client.genie.get_message_attachment_query_result(...)`
- Critical: Add column descriptions via `ALTER COLUMN COMMENT` to improve Genie SQL quality
- Critical: Add example SQL queries in Genie Space settings

**Vector Search** — For semantic retrieval:
- Use `VectorSearchClient` (separate from `WorkspaceClient`)
- `vs_client = VectorSearchClient(workspace_url=..., personal_access_token=..., disable_notice=True)`
- `index = vs_client.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)`
- `raw = index.similarity_search(query_text=..., columns=[...], num_results=10)`
- Response format: `raw["result"]["data_array"]` + `raw["manifest"]["columns"]`
- Embed multiple free-form columns (procedure, equipment, capability, description) using `databricks-gte-large-en`

**Model Serving** — LLM inference:
- `db_client.serving_endpoints.query(name=LLM_ENDPOINT, messages=[...], max_tokens=..., temperature=...)`
- Use `ChatMessage(role=ChatMessageRole.SYSTEM, content=...)` and `ChatMessage(role=ChatMessageRole.USER, content=...)`
- Primary model: `databricks-qwen3-next-80b-a3b-instruct`
- Fallback: OpenRouter `minimax/minimax-m2.1` via raw HTTP

**SQL Warehouse** — Direct SQL for geospatial and aggregate-rewrite:
- `db_client.warehouses.list()` → `warehouses[0].id`
- `db_client.statement_execution.execute_statement(warehouse_id=..., statement=..., catalog=..., schema=..., wait_timeout="30s", disposition=Disposition.INLINE)`
- Response: `resp.result.data_array` + `resp.manifest.schema.columns`

**MLflow**:
- `mlflow.set_tracking_uri("databricks")` to log to workspace
- `mlflow.set_experiment("/Shared/ghana-medical-agent")` — path-based experiment
- `@mlflow.trace(name="node_name", span_type="AGENT")` on each node function
- Span types used: `"AGENT"`, `"TOOL"`, `"RETRIEVER"`, `"LLM"`, `"CHAIN"`
- `mlflow.pyfunc.log_model(python_model=..., artifact_path="agent", ...)` for serving deployment

**Unity Catalog**:
- Default names: catalog=`hack_nation`, schema=`ghana_medical`
- Table: `ghana_facilities`
- Column descriptions via `ALTER TABLE ... ALTER COLUMN name COMMENT '...'` make Genie dramatically smarter

---

## 3. AGENT DESIGN PATTERNS

### State Schema — Exact `AgentState` Definition

```python
# src/state.py

import operator
from typing import Annotated, Literal, TypedDict

IntentType = Literal["SQL", "SEARCH", "EXTRACT", "ANOMALY", "GEO"]

class AgentState(TypedDict):
    query: str
    # NOTE: This is `intents` (plural list), NOT `intent` (singular).
    # Supports composite queries that fan-out to 2 agents simultaneously.
    intents: list[IntentType]

    sql_result: dict | None
    search_result: list | None
    extraction_result: dict | None
    anomaly_result: str | None
    geo_result: dict | None
    final_answer: str | None

    # CRITICAL: Annotated with operator.add reducer.
    # This allows parallel fan-out nodes to each append their own citations
    # without triggering INVALID_CONCURRENT_GRAPH_UPDATE.
    citations: Annotated[list, operator.add]
```

**Key design decisions in state:**
- Every result field is `Optional` / `None` so nodes that don't run don't pollute state
- `citations` uses `operator.add` reducer — mandatory for parallel fan-out
- `intents` is a list (not a string) to natively support composite routing
- `query` is overwritten by supervisor with the normalized/cleaned version

### Node Structure — Each Node's Contract

Every node:
1. Takes `state: AgentState` as sole argument
2. Returns a `dict` containing ONLY the fields it updates (not the full state)
3. Is decorated with `@mlflow.trace(name="node_name", span_type="AGENT")`
4. Appends to `citations` as a list (never replaces)
5. Has a `try/except` on all Databricks SDK calls

```python
@mlflow.trace(name="node_name", span_type="AGENT")
def some_node(state: AgentState) -> dict:
    result = call_databricks_service(state["query"])
    return {
        "some_result": result,
        "citations": [{"source": "service_name", "detail": "..."}]
    }
```

### Node Responsibilities

| Node | Intent Label | Databricks Service | Local Logic |
|---|---|---|---|
| `supervisor_node` | — | Model Serving (2 LLM calls) | Parse comma-split intents, deduplicate, cap at 2 |
| `sql_agent_node` | SQL | Genie | Detect aggregate-only results, rewrite COUNT→SELECT, fill missing regions |
| `rag_agent_node` | SEARCH | Vector Search | None |
| `idp_extraction_node` | EXTRACT | Vector Search + Model Serving | Loop over 5 facilities, extract structured JSON per facility |
| `medical_reasoning_node` | ANOMALY | Vector Search + Model Serving | None |
| `geospatial_node` | GEO | SQL Warehouse | Haversine math, desert detection, radius search |
| `synthesis_node` | — | Model Serving | Format context, append fan-out attribution note |

### Supervisor Pattern — Two-Step LLM Router

```python
# Step 1: Normalize
NORMALIZE_PROMPT = """You are a query normalizer for a Ghana healthcare facilities database.
Your ONLY job is to rewrite the user's question into clear, grammatically correct English
while preserving the original intent. Fix typos, abbreviations, and broken grammar.

DOMAIN CONTEXT — common terms the user may misspell:
  hospital, clinic, pharmacy, dentist, doctor, cardiology, ophthalmology,
  ...

RULES:
- Output ONLY the rewritten question. Nothing else.
- If the query is already correct, return it unchanged.
- Do NOT answer the question. Just rewrite it.
- Keep it concise — one clear sentence."""

# Step 2: Classify
ROUTER_PROMPT = """You classify healthcare facility questions into one or two categories.
...
COMPOSITE QUERY RULES:
- If the question clearly spans TWO categories, return BOTH separated by a comma.
  "Hospitals near Tamale with cardiology deserts" → GEO,SQL
...
Respond with ONLY the category name(s). No explanation."""

# Parse composite intents
raw_intent = query_llm(ROUTER_PROMPT, cleaned, max_tokens=20).strip().upper()
tokens = [t.strip() for t in raw_intent.replace(" ", "").split(",")]
intents = [t for t in tokens if t in VALID_INTENTS]
# Deduplicate, cap at 2, default to ["SQL"] if nothing valid
```

### How Tools Are Defined and Registered

Tools are **plain Python functions** in `src/tools/`, NOT LangChain `@tool` decorated functions. They are called directly within node functions. Each tool is independently `@mlflow.trace` decorated:

```python
@mlflow.trace(name="query_genie", span_type="TOOL")
def query_genie(question: str, timeout_seconds: int = 60) -> dict: ...

@mlflow.trace(name="query_vector_search", span_type="RETRIEVER")
def query_vector_search(query_text: str, num_results: int = 10, filters: dict | None = None) -> list[dict]: ...

@mlflow.trace(name="query_llm", span_type="LLM")
def query_llm(system_prompt: str, user_message: str, max_tokens: int = 2048, temperature: float = 0.1) -> str: ...
```

### Graph Compilation Pattern

```python
# src/graph.py
INTENT_TO_NODE = {"SQL": "SQL", "SEARCH": "SEARCH", "EXTRACT": "EXTRACT", "ANOMALY": "ANOMALY", "GEO": "GEO"}

def route_by_intents(state: AgentState) -> list[str]:
    # Returns a LIST → triggers LangGraph parallel fan-out
    return [INTENT_TO_NODE[i] for i in state["intents"] if i in INTENT_TO_NODE]

workflow = StateGraph(AgentState)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("SQL", sql_agent_node)
# ... add all 5 agent nodes + synthesis ...
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges("supervisor", route_by_intents,
    {"SQL": "SQL", "SEARCH": "SEARCH", "EXTRACT": "EXTRACT", "ANOMALY": "ANOMALY", "GEO": "GEO"})
# All agent nodes → synthesis (single convergence point)
workflow.add_edge("SQL", "synthesis")
workflow.add_edge("SEARCH", "synthesis")
workflow.add_edge("EXTRACT", "synthesis")
workflow.add_edge("ANOMALY", "synthesis")
workflow.add_edge("GEO", "synthesis")
workflow.add_edge("synthesis", END)
graph = workflow.compile()

@mlflow.trace
def run_agent(query: str) -> str:
    result = graph.invoke({"query": query, "citations": []})
    return result["final_answer"]
```

### Pydantic Models — Sponsor-Provided Schema

Three model types from the dataset creation pipeline (reference only, not directly imported into the agent):

```python
# Organization classification
class OrganizationExtractionOutput(BaseModel):
    ngos: Optional[List[str]]
    facilities: Optional[List[str]]
    other_organizations: Optional[List[str]]

# Free-form text facts (THE CORE IDP MODEL)
class FacilityFacts(BaseModel):
    procedure: Optional[List[str]]   # surgeries, diagnostics, screenings
    equipment: Optional[List[str]]   # devices, machines, infrastructure
    capability: Optional[List[str]]  # trauma levels, ICU, accreditations, staffing

# Structured facility entity
class Facility(BaseOrganization):
    facilityTypeId: Optional[Literal["hospital", "pharmacy", "doctor", "clinic", "dentist"]]
    operatorTypeId: Optional[Literal["public", "private"]]
    affiliationTypeIds: Optional[List[Literal["faith-tradition", "philanthropy-legacy",
                                              "community", "academic", "government"]]]
    description: Optional[str]
    area: Optional[int]           # VERY SPARSE — only 2 rows in dataset
    numberDoctors: Optional[int]  # VERY SPARSE — only 3 rows
    capacity: Optional[int]       # VERY SPARSE — only 23 rows

class NGO(BaseOrganization):
    countries: Optional[List[str]]  # ISO alpha-2 codes
    missionStatement: Optional[str]
    organizationDescription: Optional[str]
```

---

## 4. PROMPT ENGINEERING PATTERNS

### All Prompt Templates (Exact Text)

#### NORMALIZE_PROMPT (Supervisor — Step 1)
Purpose: Clean typos before sending to Genie (dramatically improves SQL generation)
```
You are a query normalizer for a Ghana healthcare facilities database.

Your ONLY job is to rewrite the user's question into clear, grammatically correct English
while preserving the original intent. Fix typos, abbreviations, and broken grammar.

DOMAIN CONTEXT — common terms the user may misspell:
  hospital, clinic, pharmacy, dentist, doctor, cardiology, ophthalmology,
  gynecology, pediatrics, neurology, radiology, orthopedics, oncology,
  dermatology, urology, anesthesia, pathology, surgery, equipment,
  procedure, specialties, facility, region, district, Ghana, Accra,
  Kumasi, Tamale, Korle Bu, Ashanti, Volta, Northern, Greater Accra

RULES:
- Output ONLY the rewritten question. Nothing else.
- If the query is already correct, return it unchanged.
- Do NOT answer the question. Just rewrite it.
- Keep it concise — one clear sentence.

Examples:
  "how much hopital in ghana" → "How many hospitals are in Ghana?"
  "wat servis korle bu hav" → "What services does Korle Bu Teaching Hospital offer?"
  "cardilogy desert where" → "Where are the cardiology deserts in Ghana?"
```

Called with: `query_llm(NORMALIZE_PROMPT, raw_query, max_tokens=150)`

#### ROUTER_PROMPT (Supervisor — Step 2)
Purpose: Classify into 1 or 2 intent labels, including composite queries
```
You classify healthcare facility questions into one or two categories.

CATEGORY DEFINITIONS:

SQL — counts, rankings, comparisons, distributions, lists, or correlations across the dataset.
SEARCH — a specific facility by name or services in a specific area.
EXTRACT — parse or extract structured facts from free-form text fields.
ANOMALY — data inconsistencies, mismatches, contradictions, unrealistic claims.
GEO — distances, locations, geographic coverage, cold spots, medical deserts.

COMPOSITE QUERY RULES:
- If the question clearly spans TWO categories, return BOTH separated by a comma.
  "Hospitals near Tamale with cardiology deserts" → GEO,SQL
  "Facilities claiming surgery but lacking equipment in Northern region" → ANOMALY,GEO
- Never return more than 2 categories.
- If in doubt, return just one.

Respond with ONLY the category name(s). No explanation.
Examples of valid responses: SQL | SEARCH | GEO,SQL | ANOMALY,GEO
```

Called with: `query_llm(ROUTER_PROMPT, cleaned, max_tokens=20)`

#### IDP_EXTRACTION_PROMPT (IDP Extraction Node — 30% of scoring)
Purpose: Convert raw free-form text arrays to structured JSON with confidence flags
```
You are a specialized medical facility information extractor.

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
- Empty arrays [] mean "no data found" — this is a valid signal, not missing data.
```

Called with: `query_llm(IDP_EXTRACTION_PROMPT, json.dumps(facility))` (one call per facility, up to 5 facilities)

#### MEDICAL_REASONING_PROMPT (Anomaly Detection Node)
Purpose: Cross-reference procedures vs equipment to detect contradictions
```
You are a medical facility verification expert for Ghana.

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
- FACILITY: Name and city
```

Called with: `query_llm(MEDICAL_REASONING_PROMPT, str(facilities))` where facilities is the full list (up to 20)

#### GEO_PARSE_PROMPT (Geospatial Node — Parameter Extraction)
Purpose: Extract structured geo parameters from a natural language question
```
Extract the geographic query parameters from this question.
Return JSON with these optional fields:
- "specialty": camelCase specialty name (e.g., "ophthalmology", "cardiology")
- "city": city name mentioned
- "radius_km": radius in km if mentioned (default: null)
- "query_type": one of "desert", "radius", "coverage"

Only include fields that are explicitly or strongly implied in the question.
Respond with ONLY valid JSON, no markdown.
```

Called with: `query_llm(GEO_PARSE_PROMPT, query, max_tokens=200)`

#### SYNTHESIS_PROMPT (Synthesis Node — Citation-Backed Final Answer)
Purpose: Cross-reference all agent results, produce structured markdown with evidence table
```
You are a medical data synthesis expert for Ghana healthcare facilities.

Your job is to produce a clear, citation-backed answer by CROSS-REFERENCING structured and unstructured data.

CROSS-REFERENCING RULES:
1. Compare structured field (facilityTypeId, specialties) against free-form text (procedure, equipment, capability).
   - Flag if facilityTypeId="clinic" but capabilities describe hospital-level services (trauma, ICU).
   - Flag if specialties list "ophthalmology" but no eye-related procedures or equipment found.
   - Confirm when structured and unstructured data agree (higher confidence answer).
2. Note data completeness: if a facility has procedures but zero equipment, say so explicitly.
3. Every claim MUST cite the specific facility name, field, and value that supports it.
4. When multiple data sources are provided (parallel agents), MERGE their insights.

CITATION RULES (STRICT — judges will check this):
- NEVER use generic labels like "Multiple facilities", "Various", "All N facilities", or "SQL Aggregate".
- Every row in the Supporting Evidence table MUST name a SPECIFIC facility.
- List ONE row per facility. If 13 facilities match, list all 13 by name.
- NEVER duplicate a facility — each facility name appears exactly ONCE.

OUTPUT FORMAT (Markdown):
### Answer
[Direct answer to the user's question — name specific facilities whenever possible]

### Supporting Evidence
| Facility | Region | Type | Confidence |
|---|---|---|---|
| [specific facility name] | [region] | [facility type] | High/Medium/Low |

### Data Quality Notes
[Any contradictions, gaps, or flags discovered during cross-referencing]
```

Called with: `query_llm(SYNTHESIS_PROMPT, prompt_input, max_tokens=2048)` where `prompt_input = f"User question: {user_query}\n\nAgent results:\n{context}"`

### What Prompt Structures Worked Well

1. **Strict output format specification** — Tell the LLM exactly what to return (JSON schema, markdown structure, or "ONLY the category name"). Never give open-ended output format instructions.

2. **Enumerated rules** — Use numbered/bulleted rules, not paragraphs. LLMs follow explicit enumeration better.

3. **Negative examples** ("DO NOT", "NEVER") — Explicitly forbid bad behavior. The synthesis prompt's `CITATION RULES` section prevented vague outputs like "Multiple facilities showed...".

4. **Domain constants in the prompt** — Include the actual taxonomy (camelCase specialty names, procedure-equipment dependency list) rather than asking the LLM to infer it.

5. **Treating empty as signal** — `Empty arrays [] mean "no data found" — this is a valid signal, not missing data.` This prevents hallucination of default values.

6. **Separate extraction from synthesis** — Never combine IDP extraction and synthesis in one call. Extract first, synthesize second.

7. **Low temperature** — All calls use `temperature=0.1` for deterministic, reliable outputs.

### Context Injection Strategy

The synthesis node's `_format_result_context()` function builds a structured context string from all agent results. Key pattern:

```python
# Show up to 50 rows so synthesis can cite individual facility names
for row in sr["data"][:50]:
    section += f"  {row}\n"
# Include detailed facility list if aggregate-only result was enriched
if sr.get("detail_data"):
    section += f"\n**Individual Facility Details:**\n"
    for row in sr["detail_data"][:30]:
        section += f"  {row}\n"
```

The `_format_result_context` function formats each agent result type differently:
- SQL results: include both the SQL query, text answer, raw data rows, and detail_data (if aggregate was rewritten)
- Vector Search results: include name, type, city, description[:200], specialties, procedure[:150], equipment[:150], capability[:150]
- IDP extraction: include first 500 chars per extraction
- Anomaly: include first 1000 chars
- Geo: include message, desert_regions list, covered_regions list, nearby facilities with distance_km

---

## 5. DATABRICKS-SPECIFIC PATTERNS

### Config Pattern (`src/config.py`)

The config file is the single source of truth for all Databricks credentials and client initialization. Key patterns:

```python
# Graceful fallback: app works even without Databricks credentials
if DATABRICKS_HOST and DATABRICKS_TOKEN:
    try:
        mlflow.set_tracking_uri("databricks")
        mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_PATH", "/Shared/ghana-medical-agent"))
    except Exception as e:
        logger.warning("MLflow Databricks setup failed: %s", e)
        mlflow.set_tracking_uri("mlruns")
else:
    mlflow.set_tracking_uri("mlruns")  # Local fallback

# Placeholder credentials so SDK clients can be imported module-level
db_client = WorkspaceClient(
    host=DATABRICKS_HOST or "https://placeholder.cloud.databricks.com",
    token=DATABRICKS_TOKEN or "dapi_placeholder",
)

# VectorSearchClient separately — catches init errors
try:
    vs_client = VectorSearchClient(workspace_url=..., personal_access_token=..., disable_notice=True)
except Exception:
    vs_client = None
```

**Why this matters:** Streamlit can start and render the Map and Mission Planner tabs even without Databricks access. Only the agent chat tab fails gracefully with an error message.

### Genie Integration — Complete Pattern

```python
from databricks.sdk.service.dashboards import MessageStatus

def query_genie(question: str, timeout_seconds: int = 60) -> dict:
    # 1. Start conversation
    wait = db_client.genie.start_conversation(space_id=GENIE_SPACE_ID, content=question)
    conv_id = wait.conversation_id
    msg_id = wait.message_id

    # 2. Poll until completed (2s intervals)
    for _ in range(timeout_seconds // 2):
        time.sleep(2)
        msg = db_client.genie.get_message(space_id=GENIE_SPACE_ID,
                                          conversation_id=conv_id, message_id=msg_id)
        if msg.status == MessageStatus.COMPLETED:
            break
        if msg.status == MessageStatus.FAILED:
            return {"sql": None, "text": "Query failed", "data": [], "columns": []}
    else:
        return {"sql": None, "text": "Query timed out", "data": [], "columns": []}

    # 3. Extract results from attachments
    result = {"sql": None, "description": None, "text": None, "data": [], "columns": []}
    for att in msg.attachments or []:
        if att.query:
            result["sql"] = att.query.query
            result["description"] = att.query.description
            # Fetch actual query results separately
            qr = db_client.genie.get_message_attachment_query_result(
                space_id=GENIE_SPACE_ID, conversation_id=conv_id,
                message_id=msg_id, attachment_id=att.attachment_id)
            if qr.statement_response:
                sr = qr.statement_response
                result["data"] = sr.result.data_array if sr.result else []
                result["columns"] = [c.name for c in sr.manifest.schema.columns] if sr.manifest else []
        if att.text and att.text.content:
            result["text"] = att.text.content
    return result
```

**Genie Space Setup Instructions (in Genie Space settings):**
```
Custom instructions:
  This dataset contains 987 healthcare facilities and NGOs in Ghana.
  The procedure/equipment/capability columns are JSON arrays of English strings.
  The specialties column contains JSON arrays of camelCase strings like "cardiology".
  Use LIKE '%keyword%' to search within JSON array columns.
  The region_normalized column has clean Ghana region names.

Example SQL queries to add:
  SELECT COUNT(*) FROM ghana_facilities WHERE facilityTypeId = 'hospital' AND specialties LIKE '%cardiology%';
  SELECT region_normalized, COUNT(*) as cnt FROM ghana_facilities WHERE facilityTypeId = 'hospital'
    GROUP BY region_normalized ORDER BY cnt DESC;
  SELECT name, procedure, equipment FROM ghana_facilities WHERE procedure != '[]'
    AND (equipment = '[]' OR equipment IS NULL);
```

### Vector Search Integration — Complete Pattern

```python
from databricks.vector_search.client import VectorSearchClient

vs_client = VectorSearchClient(
    workspace_url=DATABRICKS_HOST,
    personal_access_token=DATABRICKS_TOKEN,
    disable_notice=True,
)

# Index creation (run once in setup script)
vsc.create_delta_sync_index(
    endpoint_name="ghana-medical-vs",
    index_name="hack_nation.ghana_medical.ghana_facilities_index",
    source_table_name="hack_nation.ghana_medical.ghana_facilities",
    pipeline_type="TRIGGERED",
    primary_key="unique_id",
    embedding_source_columns=[
        {"name": "description", "model_endpoint_name": "databricks-gte-large-en"},
    ],
    columns_to_sync=["name", "facilityTypeId", "address_city",
                     "region_normalized", "specialties", "description",
                     "capability", "procedure", "equipment"]
)

# Query (in vector_search_tool.py)
_COLUMNS = ["name", "facilityTypeId", "address_city", "region_normalized",
            "specialties", "description", "capability", "procedure", "equipment"]

index = vs_client.get_index(endpoint_name=VS_ENDPOINT, index_name=VS_INDEX)
raw = index.similarity_search(query_text=query_text, columns=_COLUMNS, num_results=num_results)
data_array = raw.get("result", {}).get("data_array", [])
col_names = [c["name"] for c in raw.get("manifest", {}).get("columns", [])]
results = [dict(zip(col_names, row)) for row in data_array]
```

### Model Serving — LLM Call with Fallback

```python
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

LLM_ENDPOINT = "databricks-qwen3-next-80b-a3b-instruct"

try:
    response = db_client.serving_endpoints.query(
        name=LLM_ENDPOINT,
        messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=ChatMessageRole.USER, content=user_message),
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content
except Exception as e:
    logger.warning("Databricks Model Serving failed: %s — falling back to OpenRouter", e)
    # OpenRouter fallback
    resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={"model": "minimax/minimax-m2.1", "messages": [...], "max_tokens": max_tokens})
    return resp.json()["choices"][0]["message"]["content"]
```

### `model_config.yaml` — What It Contains and Why

```yaml
# src/serving/model_config.yaml
llm_endpoint: "databricks-qwen3-next-80b-a3b-instruct"
llm_parameters:
  max_tokens: 2048
  temperature: 0.1

openrouter_model: "minimax/minimax-m2.1"

genie_space_id: "${GENIE_SPACE_ID}"
vector_search_index: "${VECTOR_SEARCH_INDEX}"
vector_search_endpoint: "${VECTOR_SEARCH_ENDPOINT}"
databricks_catalog: "hack_nation"
databricks_schema: "ghana_medical"

mlflow_experiment_path: "/Shared/ghana-medical-agent"
agent_name: "ghana-medical-agent"
```

**Why:** This file is consumed by `mlflow.models.ModelConfig(development_config=str(_CONFIG_PATH))` when deploying via Mosaic AI Agent Framework. It parametrizes the agent across environments without code changes. Secret values use `${ENV_VAR}` substitution.

### Mosaic AI Agent Framework Deployment (Stretch Goal Pattern)

```python
# src/serving/agent_wrapper.py
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse, ResponsesAgentStreamEvent

class YourAgent(ResponsesAgent):
    def __init__(self):
        from src.graph import graph
        self.graph = graph  # Compiled once, reused across requests

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        user_query = self._extract_query(request)
        result = self.graph.invoke({"query": user_query, "citations": []})
        answer = result.get("final_answer", "No answer produced.")
        output_item = self.create_text_output_item(text=answer, id=str(uuid4()))
        return ResponsesAgentResponse(output=[output_item])

    def predict_stream(self, request) -> Generator:
        # Run sync, stream the final answer word-by-word
        result = self.graph.invoke({"query": self._extract_query(request), "citations": []})
        answer = result.get("final_answer", "No answer produced.")
        item_id = str(uuid4())
        for i, word in enumerate(answer.split(" ")):
            yield self.create_text_delta(delta=word + (" " if i < len(words) - 1 else ""), item_id=item_id)
        yield ResponsesAgentStreamEvent(type="response.output_item.done",
                                        item=self.create_text_output_item(text=answer, id=item_id))
```

```python
# src/serving/log_agent.py — Deployment
mlflow.pyfunc.log_model(
    python_model="src/serving/agent_wrapper.py",
    artifact_path="agent",
    model_config="src/serving/model_config.yaml",
    pip_requirements=["mlflow>=3.1.3", "databricks-sdk", "databricks-vectorsearch",
                      "databricks-agents>=1.2.0", "langgraph>=0.2", "python-dotenv", "requests"],
    code_paths=["src/"],  # Include full src/ package
)
# Register in Unity Catalog
mlflow.register_model(model_uri, "hack_nation.ghana_medical.medical_intelligence_agent")
# Deploy
from databricks import agents
agents.deploy(UC_MODEL_NAME, model_uri, environment_vars={...}, scale_to_zero=True)
```

---

## 6. DATA PIPELINE PATTERNS

### Raw Data Loading and Preprocessing

The preprocessing runs **once** in `scripts/setup_databricks.py` (run as a Databricks notebook or locally):

```python
# Key preprocessing steps in order:
# 1. Fix typo
df = df.withColumn("facilityTypeId",
    F.when(F.col("facilityTypeId") == "farmacy", "pharmacy").otherwise(F.col("facilityTypeId")))

# 2. Normalize regions (53 dirty variations → 16 clean official names)
region_map = {
    "Greater Accra Region": "Greater Accra", "Accra": "Greater Accra",
    "ASHANTI": "Ashanti", "Ashanti Region": "Ashanti",
    "Western Region": "Western", "Central Region": "Central",
    # ... (full map has 53 entries covering all variants)
}

# 3. Parse free-form JSON strings
# procedure/equipment/capability columns are stored as JSON strings: '["item1", "item2"]'
# Parse with json.loads() during preprocessing

# 4. Deduplicate by name + city (71 names appear >1 time)
# Merge parsed arrays for duplicate entries

# 5. Add unique_id column (required as primary_key for Vector Search index)
df = df.withColumn("unique_id", F.monotonically_increasing_id().cast("string"))

# 6. Save as Delta table
df.write.format("delta").mode("overwrite") \
    .option("delta.enableChangeDataFeed", "true") \
    .saveAsTable("hack_nation.ghana_medical.ghana_facilities")

# 7. Add column descriptions for Genie intelligence
# ALTER TABLE ... ALTER COLUMN name COMMENT '...'
```

### Geospatial Data Pattern

**No lat/lon in the raw dataset** — all geocoding is done via a static lookup file:

```json
// data/ghana_city_coords.json (117 entries, format: {"CityName": [lat, lon]})
{
  "Accra": [5.6037, -0.1870],
  "Kumasi": [6.6885, -1.6244],
  "Tamale": [9.4075, -0.8533],
  ...
}
```

```python
# Haversine implementation (pure Python, no dependencies)
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# Desert detection (pure Python set operations)
def find_desert_regions(facilities: list[dict], specialty: str) -> list[str]:
    all_regions, covered_regions = set(), set()
    for f in facilities:
        region = f.get("region_normalized")
        if not region:
            continue
        all_regions.add(region)
        specialties_raw = f.get("specialties") or "[]"
        specs = json.loads(specialties_raw) if isinstance(specialties_raw, str) else []
        if specs and specialty in specs:
            covered_regions.add(region)
    return sorted(all_regions - covered_regions)
```

### RAG Pipeline Structure

```
User query
  → query_vector_search(query, num_results=5)  # 5 for IDP extraction, 10 for SEARCH, 20 for ANOMALY
  → index.similarity_search(query_text=..., columns=[...], num_results=...)
  → Convert data_array + manifest columns → list[dict]
  → (For IDP) loop over each facility dict → query_llm(IDP_EXTRACTION_PROMPT, json.dumps(facility))
  → (For synthesis) format all results into context string
  → query_llm(SYNTHESIS_PROMPT, context, max_tokens=2048)
```

### SQL Agent's Aggregate-Rewrite Pattern (Critical for Good Answers)

When Genie returns only a COUNT (e.g., "13 hospitals have cardiology"), the SQL agent rewrites the SQL to get actual facility names for citation purposes:

```python
def _is_aggregate_only(result: dict) -> bool:
    data = result.get("data", [])
    cols = [c.lower() for c in result.get("columns", [])]
    if len(data) <= 1 and len(cols) <= 2:
        count_keywords = {"count", "cnt", "total", "sum", "avg", "min", "max"}
        if any(kw in c for c in cols for kw in count_keywords):
            return True
        if len(data) == 1 and len(data[0]) == 1:
            try: int(data[0][0]); return True
            except: pass
    return False

def _rewrite_count_to_select(sql: str) -> str | None:
    pattern = re.compile(r"SELECT\s+COUNT\s*\([^)]*\).*?FROM", re.IGNORECASE | re.DOTALL)
    if not pattern.search(sql):
        return None
    rewritten = pattern.sub("SELECT name, region_normalized, facilityTypeId, address_city FROM", sql, count=1)
    rewritten = re.sub(r"\bORDER\s+BY\s+.*$", "", rewritten, flags=re.IGNORECASE)
    if "LIMIT" not in rewritten.upper():
        rewritten = rewritten.rstrip().rstrip(";") + " LIMIT 30"
    return rewritten
```

---

## 7. WHAT TO REUSE VERBATIM IN NEXT PROJECT

### Files to Copy With Minimal Changes

| File | What to Change |
|---|---|
| `src/state.py` | Field names for new domain result types; keep `intents`, `final_answer`, `citations` as-is |
| `src/graph.py` | Node names to match new domain (keep pattern: supervisor → fan-out → synthesis → END) |
| `src/config.py` | `LLM_ENDPOINT`, `GENIE_SPACE_ID`, `VS_INDEX`, `VS_ENDPOINT`, `CATALOG`, `SCHEMA` values only |
| `src/tools/model_serving_tool.py` | Zero changes — it's a generic LLM caller with OpenRouter fallback |
| `src/tools/genie_tool.py` | Zero changes — it's a generic Genie wrapper |
| `src/tools/vector_search_tool.py` | Only `_COLUMNS` list (the columns to return from your domain's Delta table) |
| `src/nodes/supervisor.py` | The NORMALIZE_PROMPT domain context section; the intent category definitions |
| `src/nodes/synthesis.py` | The SYNTHESIS_PROMPT cross-referencing rules for your new domain |
| `src/serving/agent_wrapper.py` | Class name only |
| `src/serving/model_config.yaml` | All values |
| `src/serving/log_agent.py` | `UC_MODEL_NAME` value only |
| `src/nodes/geospatial.py` | Haversine + desert detection math functions are domain-agnostic |
| `tests/test_config.py` | Zero changes |
| `tests/test_tools.py` | Query strings only |
| `tests/test_graph.py` | Query strings and expected intent labels |
| `.env.example` | All variable names stay the same |

### Utility Functions Worth Keeping

```python
# From src/nodes/geospatial.py — pure math, always reusable
haversine_km(lat1, lon1, lat2, lon2) -> float
find_desert_regions(facilities, specialty) -> list[str]
find_facilities_within_radius(facilities, center_lat, center_lon, radius_km) -> list[dict]

# From src/nodes/sql_agent.py — handles Genie's aggregate-only responses
_is_aggregate_only(result: dict) -> bool
_rewrite_count_to_select(sql: str) -> str | None
_run_sql_direct(sql: str) -> tuple[list, list]

# From src/serving/agent_wrapper.py — message extraction
_extract_query(request: ResponsesAgentRequest) -> str

# From src/nodes/synthesis.py — builds LLM context from all agent results
_format_result_context(state: AgentState) -> str
_active_agents(state: AgentState) -> list[str]
```

### Exact Pydantic Model Structure to Replicate

The `FacilityFacts` three-field pattern is the key structural insight for any domain with unstructured text:

```python
class DomainFacts(BaseModel):
    """Adapt these three categories to your domain's unstructured text."""
    procedure: Optional[List[str]] = Field(
        description="Specific actions/operations performed — must be declarative English statements")
    equipment: Optional[List[str]] = Field(
        description="Physical assets/tools — include specific models when available")
    capability: Optional[List[str]] = Field(
        description="Level/type of service delivery — accreditations, units, programs, staffing")
```

The three-part split (what they **do** / what they **have** / what level they **can** deliver) maps cleanly to almost any domain.

### The `citations: Annotated[list, operator.add]` Pattern

This is the most important LangGraph pattern to carry forward. Without `operator.add`, parallel fan-out raises `INVALID_CONCURRENT_GRAPH_UPDATE`:

```python
from typing import Annotated
import operator

class AgentState(TypedDict):
    citations: Annotated[list, operator.add]  # Each parallel node appends; never replaces
```

---

## 8. WHAT TO IMPROVE NEXT TIME

### Architectural Weaknesses (Inferred from Code)

1. **`intents` vs `intent` mismatch in tests** — `state.py` uses `intents: list[IntentType]` but some test files assert `result["intent"]` (singular). This was a schema evolution bug (started as singular, moved to list for fan-out) that wasn't propagated to all tests. **Fix next time:** Define the state schema first and write the tests against it before implementing nodes.

2. **IDP extraction loops serially over facilities** — `idp_extraction_node` calls `query_llm` in a `for` loop over 5 facilities. Under hackathon time pressure this works, but it means 5 sequential LLM calls. **Fix next time:** Use `asyncio.gather()` with async LLM calls or batch the facilities into one prompt.

3. **Geospatial city coords coverage** — Only 117 cities in `ghana_city_coords.json`. Many facilities have cities not in the lookup, silently getting no coordinates (and thus excluded from radius searches). **Fix next time:** Build the lookup from the actual city list in the dataset, not a manually compiled file.

4. **`medical_specialties.py` imports `fdr` package** — The sponsor-provided `medical_specialties.py` file imports from `from fdr.config.medical_specialties import ...` which is not in the repo. This file is unusable as-is. **Fix next time:** Vendor the dependency or inline the constants.

5. **setup_databricks.py and .env.example naming mismatch** — `setup_databricks.py` writes `OPENAI_API_KEY` but `.env.example` documents `OPENROUTER_API_KEY`. The setup script and example env were written independently and never reconciled. **Fix next time:** Write `.env.example` first, then write the setup script to match it.

6. **No streaming in the main agent** — The Streamlit app shows `st.spinner("Running agent graph...")` for the entire duration. For long queries (IDP extraction with 5 LLM calls), this can be 30+ seconds of blank spinner. **Fix next time:** Use LangGraph's streaming mode or at least `st.write_stream()` for the synthesis answer.

7. **Synthesis context truncation** — `synthesis_node` passes up to 50 SQL rows, 10 vector search results, and 5 IDP extractions. For large datasets this can hit context window limits. **Fix next time:** Implement smarter context compression — rank results by relevance score before passing to synthesis.

8. **No session memory** — Each query is fully stateless. For multi-turn conversations (common in planning workflows), the agent has no memory of previous answers. **Fix next time:** Add `messages: Annotated[list, operator.add]` to state and include conversation history in the supervisor prompt.

9. **Region fill fallback is fragile** — `_fill_region()` in `sql_agent.py` defaults missing regions to `"Greater Accra"`, which silently biases geospatial results. **Fix next time:** Use `"Unknown"` as the default and filter explicitly in downstream logic.

### Patterns That Were Brittle

1. **Genie polling loop** — `time.sleep(2)` polling for up to `timeout_seconds // 2` iterations adds latency. If Genie takes 50+ seconds, queries time out. Under hackathon demo conditions this caused visible delays.

2. **JSON parsing from LLM responses** — The geo node does `json.loads(parsed_raw.strip().strip("```json").strip("```"))` — a fragile string manipulation to remove markdown code fences. **Fix next time:** Use a Pydantic model with `model_validate_json()` and instruct the LLM to return raw JSON.

3. **`str(facilities)` as LLM input** — `medical_reasoning_node` calls `query_llm(MEDICAL_REASONING_PROMPT, str(facilities))` — using Python's default list-to-string conversion, which is ugly and wastes tokens. **Fix next time:** Use `json.dumps(facilities, indent=2)`.

---

## 9. CURSOR RULES FOR NEW PROJECT

Save this as `.cursor/rules/architecture.mdc` in the new project:

```markdown
---
description: Architecture and coding conventions for Databricks-track hackathon projects
globs: ["src/**/*.py", "tests/**/*.py"]
alwaysApply: true
---

# Databricks Hackathon Architecture Rules

## Agent Graph Pattern
- Every project uses a LangGraph StateGraph with this topology:
  `supervisor → conditional fan-out → 1-2 agent nodes → synthesis → END`
- The supervisor node performs TWO LLM calls: (1) normalize query, (2) classify intent
- The conditional edge function `route_by_intents` MUST return a `list[str]` to support fan-out
- All agent nodes converge at a single `synthesis` node before END
- Never add edges that bypass synthesis

## State Schema Rules
- State is defined as a `TypedDict` in `src/state.py` — single source of truth
- `intents` is ALWAYS a `list[IntentType]` (plural), never a single string
- `citations` MUST use `Annotated[list, operator.add]` for parallel fan-out safety
- Every result field (sql_result, search_result, etc.) is `dict | None` or `list | None`
- Never add `Optional` wrappers — use `| None` union syntax (Python 3.10+)

## Node Contract Rules
- Every node function signature: `def node_name(state: AgentState) -> dict:`
- Every node is decorated with `@mlflow.trace(name="node_name", span_type="AGENT")`
- Every node returns ONLY the fields it updates (never returns the full state)
- Citations append pattern: `"citations": [{"source": "...", "detail": "..."}]` (list, not dict)
- Every Databricks SDK call is wrapped in try/except with logger.warning on failure

## Tool Rules
- All tools are plain Python functions in `src/tools/` (NOT LangChain @tool decorated)
- Tool naming convention: `query_<service>` (e.g., `query_genie`, `query_vector_search`, `query_llm`)
- Tools use `@mlflow.trace(name="query_<service>", span_type="TOOL"|"RETRIEVER"|"LLM")`
- `query_llm` always accepts `(system_prompt, user_message, max_tokens=2048, temperature=0.1)`
- `query_llm` always tries Databricks first, falls back to OpenRouter

## Prompt Engineering Rules
- Every prompt specifies an EXACT output format (JSON schema or Markdown template)
- Prompts use numbered/bulleted rules, NOT paragraphs
- Prompts explicitly forbid bad behaviors with "NEVER", "DO NOT" language
- All LLM calls use `temperature=0.1` for deterministic outputs
- Empty arrays `[]` are explicitly called out as valid signals in extraction prompts
- Never combine extraction and synthesis in a single LLM call

## Config Rules
- All credentials load from `.env` via `load_dotenv()` at top of `src/config.py`
- SDK clients are created eagerly with placeholder credentials so modules can import at top level
- MLflow falls back to local `mlruns/` if Databricks credentials are absent
- The app MUST start even without Databricks credentials (graceful degradation)

## File Structure (must match exactly)
```
src/
├── app.py           # Streamlit entry point only — no business logic
├── config.py        # Credentials, SDK client init, MLflow setup
├── state.py         # AgentState TypedDict — define this FIRST
├── graph.py         # StateGraph build + run_agent() with @mlflow.trace
├── data_loader.py   # Local data loading and fallback CSV
├── map_component.py # Folium map builder — no agent logic here
├── nodes/
│   ├── supervisor.py
│   ├── sql_agent.py
│   ├── rag_agent.py
│   ├── idp_extraction.py
│   ├── medical_reasoning.py
│   ├── geospatial.py
│   └── synthesis.py
├── tools/
│   ├── genie_tool.py
│   ├── vector_search_tool.py
│   └── model_serving_tool.py
└── serving/
    ├── agent_wrapper.py  # ResponsesAgent for Mosaic AI deployment
    ├── log_agent.py      # mlflow.pyfunc.log_model + register + deploy
    └── model_config.yaml # Parametrize across environments
```

## Testing Rules
- Tests are split by phase: connectivity → graph/routing → node contracts → local math → e2e
- test_config.py: verify Databricks connection with a real SDK call
- test_tools.py: smoke test each Databricks service with a trivial query
- test_graph.py: verify graph compiles + supervisor routes correctly
- test_nodes.py: verify each node returns expected state keys
- test_geospatial.py: verify Haversine math with known distances
- test_e2e.py: run 5 demo queries, require at least 3/5 to return non-empty answers
- MVD gate: run test_e2e.py before moving from Core to Surface phase

## Naming Conventions
- Intent labels: ALL_CAPS (SQL, SEARCH, EXTRACT, ANOMALY, GEO)
- Node functions: `<role>_node(state: AgentState) -> dict`
- Tool functions: `query_<service>(...)-> dict|list|str`
- State fields: `<role>_result` for agent outputs (sql_result, search_result, etc.)
- Citation source keys: `"source": "<service>"` (genie, vector_search, idp_extraction, etc.)

## Databricks Service Naming
- Catalog: `hack_nation` (or project-specific equivalent)
- Schema: `<domain>_data` (e.g., `ghana_medical`, `supply_chain`)
- Table: `<domain>_facilities` or `<domain>_records`
- Vector Search endpoint: `<domain>-vs`
- Vector Search index: `<catalog>.<schema>.<table>_index`
- MLflow experiment: `/Shared/<domain>-agent`
- Unity Catalog model: `<catalog>.<schema>.<agent_name>`
```

---

## 10. STARTER CHECKLIST FOR NEW HACKATHON

### Hour 0-1: Judge Alignment (Before Writing Any Code)

- [ ] Read the full challenge brief; extract evaluation criteria with percentage weights
- [ ] Create a "feature → score bucket" table (which features hit which scoring criterion)
- [ ] Define exactly 5 demo queries that each prove a different scoring area
- [ ] Identify which Databricks services are required/recommended by the challenge
- [ ] Create `AGENT.md` with mission statement, rubric table, architecture sketch, demo script

### Day 1 Files to Create (In This Order)

1. **`AGENT.md`** — Mission, rubric, architecture diagram, "what runs where" table, data quality issues, milestones, must-have query bank, anti-patterns, 5-minute demo script, phase DoD
2. **`README.md`** — Quick start, prerequisites, `.env` setup, how to run
3. **`data_flow.md`** — End-to-end pipeline from raw data to UI output
4. **`.env.example`** — All environment variable names with descriptions
5. **`requirements.txt`** — All dependencies pinned
6. **`src/state.py`** — `AgentState` TypedDict (define this FIRST before any other src/ file)
7. **`src/config.py`** — Databricks client init + MLflow setup + graceful fallback
8. **`src/tools/model_serving_tool.py`** — `query_llm()` with OpenRouter fallback
9. **`src/tools/genie_tool.py`** — `query_genie()` with polling loop
10. **`src/tools/vector_search_tool.py`** — `query_vector_search()` 
11. **`tests/test_config.py`** — Databricks connection smoke test
12. **`tests/test_tools.py`** — Genie, Vector Search, Model Serving smoke tests

### Phase 1: Foundation — Databricks Setup (Hours 1-6)

- [ ] Create Databricks Free Edition workspace (signup.databricks.com)
- [ ] Upload CSV to Databricks Volume
- [ ] Run data cleaning: fix typos, normalize regions, handle duplicates, parse JSON strings
- [ ] Create Delta table with `delta.enableChangeDataFeed = true`
- [ ] Add `ALTER COLUMN COMMENT` for EVERY column (critical for Genie quality)
- [ ] Create Vector Search endpoint: `vsc.create_endpoint(name="<domain>-vs", endpoint_type="STANDARD")`
- [ ] Create Vector Search index with auto-embedding on free-form text column(s)
- [ ] Create Genie Space → add table → add custom instructions → add 3+ example SQL queries → note Space ID
- [ ] Populate `.env` with: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_CATALOG`, `DATABRICKS_SCHEMA`, `GENIE_SPACE_ID`, `VECTOR_SEARCH_INDEX`, `VECTOR_SEARCH_ENDPOINT`
- [ ] Run `pytest tests/test_config.py tests/test_tools.py` — all must pass before Phase 2

### Phase 2: Core — LangGraph Agent Graph (Hours 6-12)

- [ ] Implement `src/nodes/supervisor.py` with normalize + classify (2-step LLM)
- [ ] Implement `src/nodes/sql_agent.py` (calls Genie, handles aggregate-only results)
- [ ] Implement `src/nodes/rag_agent.py` (calls Vector Search)
- [ ] Implement `src/nodes/idp_extraction.py` (Vector Search + LLM extraction loop)
- [ ] Implement `src/nodes/medical_reasoning.py` (domain anomaly detection)
- [ ] Implement `src/nodes/geospatial.py` (local math + direct SQL)
- [ ] Implement `src/nodes/synthesis.py` (SYNTHESIS_PROMPT + context formatter)
- [ ] Implement `src/graph.py` (StateGraph + `route_by_intents` returning `list[str]`)
- [ ] Run `pytest tests/test_graph.py tests/test_nodes.py`

### Phase 2.5: MVD Gate (Hour 12 — Non-Negotiable)

- [ ] Run all 5 demo queries through `run_agent()` 
- [ ] Require 3/5 to return non-empty markdown answers
- [ ] **If gate fails: STOP. Debug routing and Databricks connectivity before any polish**
- [ ] Run `pytest tests/test_e2e.py`

### Phase 3: Surface — UI + Visuals + Citations (Hours 12-20)

- [ ] Implement `src/app.py` — 3-tab Streamlit layout: Agent Chat, Mission Planner, Map
- [ ] Implement `src/map_component.py` — Folium with color-coded markers by type
- [ ] Add medical desert overlay (translucent red circles on desert regions)
- [ ] Add Mission Planner tab: summary cards, specialty dropdown, priority tiers (red/yellow/green), flagged facilities
- [ ] Add `@mlflow.trace` decorators to all nodes and tools (if not already done)
- [ ] Add `try/except` on ALL Databricks SDK calls
- [ ] Run `pytest tests/test_geospatial.py`
- [ ] Manually verify all 5 demo queries end-to-end

### Phase 4: Demo Hardening (Hours 20-24)

- [ ] Pre-compute and cache expensive startup queries in `st.session_state`
- [ ] Add sidebar with 5 example query buttons (clicking sets `st.session_state.query`)
- [ ] Write and time the 5-minute demo script (practice 3x)
- [ ] Add graceful error messages for Databricks failures
- [ ] Check MLflow traces in Databricks UI for citation trail completeness
- [ ] Optionally implement Mosaic AI Agent deployment via `src/serving/log_agent.py`

### Critical Anti-Patterns to Avoid

1. **Do NOT start with the UI** — Core agent graph must work first
2. **Do NOT skip column descriptions** in Unity Catalog — Genie generates much worse SQL without them
3. **Do NOT use `intent: str`** in state — Use `intents: list` from day 1 for fan-out readiness
4. **Do NOT combine extraction + synthesis in one prompt** — Separate them always
5. **Do NOT hardcode any answers** — System must generalize to new queries
6. **Do NOT treat `[]` (empty array) as missing data** — Explicitly flag it as "no data found" signal
7. **Do NOT build a custom SQL agent** — Use Genie; it already understands your column descriptions
8. **Do NOT start fan-out before MVD gate passes** — Linear routing (1 agent at a time) is the MVP
9. **Do NOT skip the `citations: Annotated[list, operator.add]` pattern** — Parallel nodes will crash without it
10. **Do NOT skip the normalize step in supervisor** — Dirty queries produce bad Genie SQL

### 5-Minute Demo Script Template

| Time | Action | Scoring Criteria Hit |
|---|---|---|
| 0:00–0:45 | Problem statement: show the raw data (messy free-form text), explain why it's hard | Social Impact (25%) |
| 0:45–1:30 | Run IDP extraction query: "Extract capabilities for [Top Facility Name]" → show structured facts | **IDP Innovation (30%)** |
| 1:30–2:30 | Run anomaly query: "Which facilities claim surgery but lack equipment?" → show VERDICT/REASON/EVIDENCE | Technical Accuracy (35%) |
| 2:30–3:30 | Show Mission Planner tab: specialty dropdown → desert regions → deployment priorities | Social Impact + UX |
| 3:30–4:15 | Show map: color markers + red desert overlays | Social Impact (25%) |
| 4:15–5:00 | Show MLflow trace in Databricks UI: step-level citations for last query | Technical Accuracy (35%) |

**Closing line template:** "Every data point we extract represents a [domain-specific person] who could receive [service] sooner."

---

## Appendix: Environment Variable Reference

```bash
# === Databricks (primary backend) ===
DATABRICKS_HOST=https://dbc-XXXXX.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_CATALOG=hack_nation
DATABRICKS_SCHEMA=ghana_medical  # or your domain schema

# === Databricks Services ===
GENIE_SPACE_ID=...                # From Genie Space URL
VECTOR_SEARCH_INDEX=hack_nation.ghana_medical.ghana_facilities_index
VECTOR_SEARCH_ENDPOINT=ghana-medical-vs

# === MLflow ===
MLFLOW_EXPERIMENT_PATH=/Shared/ghana-medical-agent
LLM_ENDPOINT=databricks-qwen3-next-80b-a3b-instruct

# === LLM Fallback ===
OPENROUTER_API_KEY=sk-or-v1-...   # Optional — minimax/minimax-m2.1
```

## Appendix: Medical Specialty Taxonomy (camelCase)

```
internalMedicine, familyMedicine, pediatrics, cardiology, generalSurgery,
emergencyMedicine, gynecologyAndObstetrics, orthopedicSurgery, dentistry,
ophthalmology, otolaryngology, radiology, pathology, anesthesia,
criticalCareMedicine, nephrology, medicalOncology, infectiousDiseases,
physicalMedicineAndRehabilitation, hospiceAndPalliativeInternalMedicine,
neonatologyPerinatalMedicine, endocrinologyAndDiabetesAndMetabolism,
plasticSurgery, cardiacSurgery, geriatricsInternalMedicine, orthodontics
```

Common term mappings:
- "Emergency", "ER" → `emergencyMedicine`
- "Surgery" (generic) → `generalSurgery`
- "Eye", "Ophthalmic" → `ophthalmology`
- "Cardiac Surgery" → `cardiacSurgery`
- "Pediatric", "Children" → `pediatrics`
- "Maternity", "Obstetric" → `gynecologyAndObstetrics`
- "Trauma" → `criticalCareMedicine`
- "Oncology", "Cancer" → `medicalOncology`
