# AGENT.md — Hack Nation: Bridging Medical Deserts (Databricks Track)

---

## Mission Statement

Build an **Intelligent Document Parsing (IDP) Agent** that extracts, verifies, and reasons over medical facility data from Ghana (provided by the Virtue Foundation) to identify **medical deserts** and infrastructure gaps. The system must parse unstructured free-form text, synthesize it with structured facility schemas, detect anomalies, and present findings through an interactive map + natural language planning interface.

---

## Evaluation Criteria

| Criterion              | Weight  | What Wins                                                                                                                              |
| ---------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Technical Accuracy** | **35%** | Agent reliably handles "Must Have" queries from the question bank. Detects anomalies in facility data.                                 |
| **IDP Innovation**     | **30%** | Extracts + synthesizes info from unstructured free-form text (procedure, equipment, capability columns). Goes beyond keyword matching. |
| **Social Impact**      | **25%** | Effectively identifies medical deserts. Aids resource allocation decisions. Compelling narrative.                                      |
| **User Experience**    | **10%** | Intuitive for non-technical NGO planners. Natural language interface.                                                                  |

---

## Architecture — Databricks-Native

The challenge recommends this base stack:

> **Agentic orchestrator:** LangGraph, LlamaIndex, CrewAI
> **ML lifecycle:** MLflow
> **RAG:** Databricks, FAISS, LanceDB
> **Text2SQL:** Genie

Our architecture: **LangGraph** orchestrates a multi-agent graph locally. Each agent node calls **Databricks Free Edition** services as tools. **MLflow** traces every step. **Streamlit** renders the frontend.

```mermaid
flowchart TD
    subgraph FE["Frontend (Local)"]
        ST["Streamlit App"]
        MAP["Folium Map"]
    end

    subgraph LG["LangGraph Agent Graph (Local)"]
        SUP["Supervisor Node<br/><i>Intent classification + routing</i>"]
        SQL_N["SQL Agent Node<br/><i>Calls Genie</i>"]
        VEC_N["RAG Agent Node<br/><i>Calls Vector Search</i>"]
        MED_N["Medical Reasoning Node<br/><i>Calls Model Serving</i>"]
        GEO_N["Geospatial Node<br/><i>Local Haversine</i>"]
        SYN["Synthesis Node<br/><i>Merges results + citations</i>"]
    end

    subgraph DB["Databricks Free Edition (Remote)"]
        UC["Unity Catalog — Delta Table"]
        GN["Genie — Text-to-SQL"]
        VS["Vector Search — RAG"]
        MS["Model Serving — Llama 3.3 70B"]
        ML["MLflow — Tracing + Citations"]
    end

    ST -->|"User query"| SUP
    SUP -->|STRUCTURED| SQL_N
    SUP -->|SEMANTIC| VEC_N
    SUP -->|ANOMALY| MED_N
    SUP -->|GEOSPATIAL| GEO_N
    SQL_N -->|"SDK call"| GN
    VEC_N -->|"SDK call"| VS
    MED_N -->|"SDK call"| MS
    GN --> UC
    VS --> UC
    SQL_N --> SYN
    VEC_N --> SYN
    MED_N --> SYN
    GEO_N --> SYN
    SYN --> ST
    SYN -->|"Log trace"| ML
    ST --> MAP

    style FE fill:#EBF5FB,stroke:#2E86C1
    style LG fill:#E8F8F5,stroke:#1ABC9C
    style DB fill:#FEF9E7,stroke:#F39C12
```

### How Each Databricks Feature Maps to the Challenge

| Challenge Requirement | Databricks Feature | What It Does | Docs |
|---|---|---|---|
| **Structured queries** (counts, aggregations) | **Genie** (Text-to-SQL) | Takes natural language, generates SQL, executes against Delta table, returns results | [docs.databricks.com/en/genie](https://docs.databricks.com/en/genie/) |
| **Semantic search** over free-form text | **Mosaic AI Vector Search** | Auto-embeds procedure/equipment/capability columns, returns top-k matches by semantic similarity | [docs.databricks.com/en/generative-ai/vector-search](https://docs.databricks.com/en/generative-ai/vector-search) |
| **Anomaly detection** (procedure-equipment gaps) | **Model Serving** (Llama 3.3 70B) | LLM reasons over facility data to detect mismatches between claimed procedures and listed equipment | [docs.databricks.com/en/machine-learning/model-serving](https://docs.databricks.com/en/machine-learning/model-serving) |
| **Data storage** with governance | **Unity Catalog** | Managed Delta table with column descriptions — makes Genie smarter and shows data governance | [docs.databricks.com/en/data-governance/unity-catalog](https://docs.databricks.com/en/data-governance/unity-catalog) |
| **Citation trail** (which data produced each answer) | **MLflow Tracing** | Logs inputs/outputs of each step, creating an audit trail of which rows were used | [docs.databricks.com/en/mlflow](https://docs.databricks.com/en/mlflow) |
| **Data cleaning** + geocoding | **Notebooks** | Python notebook for one-time CSV cleaning, region normalization, geocoding, upload to Unity Catalog | [docs.databricks.com/en/notebooks](https://docs.databricks.com/en/notebooks) |

### What Runs Where

| Component | Runs On | Technology | Docs |
|---|---|---|---|
| **Agent orchestration** | Local | LangGraph (state graph with supervisor routing) | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/) |
| **Frontend** | Local | Streamlit + Folium map | [docs.streamlit.io](https://docs.streamlit.io/) |
| **Geospatial** | Local | Python Haversine + numpy | — |
| **Text-to-SQL** | Databricks | Genie | [docs.databricks.com/en/genie](https://docs.databricks.com/en/genie/) |
| **RAG / Semantic search** | Databricks | Vector Search | [docs.databricks.com/en/generative-ai/vector-search](https://docs.databricks.com/en/generative-ai/vector-search) |
| **LLM inference** | Databricks | Model Serving (Llama 3.3 70B) | [docs.databricks.com/en/machine-learning/model-serving](https://docs.databricks.com/en/machine-learning/model-serving) |
| **Agent tracing** | Databricks | MLflow Tracing | [docs.databricks.com/en/mlflow](https://docs.databricks.com/en/mlflow) |
| **Data storage** | Databricks | Unity Catalog Delta table | [docs.databricks.com/en/data-governance/unity-catalog](https://docs.databricks.com/en/data-governance/unity-catalog) |

---

## Tech Stack

| Layer | Technology | Docs |
|---|---|---|
| **Agent Orchestration** | **LangGraph** (multi-agent state graph) | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/) |
| **Data Storage** | Databricks Unity Catalog (Delta table) | [docs.databricks.com/en/data-governance/unity-catalog](https://docs.databricks.com/en/data-governance/unity-catalog) |
| **Text-to-SQL** | Databricks Genie | [docs.databricks.com/en/genie](https://docs.databricks.com/en/genie/) |
| **RAG / Semantic Search** | Databricks Mosaic AI Vector Search | [docs.databricks.com/en/generative-ai/vector-search](https://docs.databricks.com/en/generative-ai/vector-search) |
| **LLM** | Databricks Model Serving (Llama 3.3 70B) | [docs.databricks.com/en/machine-learning/model-serving](https://docs.databricks.com/en/machine-learning/model-serving) |
| **Embeddings** | Databricks `gte-large-en` (auto via Vector Search) | [docs.databricks.com/en/generative-ai/vector-search](https://docs.databricks.com/en/generative-ai/vector-search) |
| **ML Lifecycle / Tracing** | MLflow Tracing | [docs.databricks.com/en/mlflow](https://docs.databricks.com/en/mlflow) |
| **Data Cleaning** | Databricks Notebooks (Python + Spark SQL) | [docs.databricks.com/en/notebooks](https://docs.databricks.com/en/notebooks) |
| **Frontend** | Streamlit | [docs.streamlit.io](https://docs.streamlit.io/) |
| **Map** | Folium + streamlit-folium | [python-visualization.github.io/folium](https://python-visualization.github.io/folium/) |
| **Geospatial** | Python (Haversine, numpy) — local | — |
| **Language** | Python 3.11+ | — |

### .env.example

```bash
# === Databricks (primary backend) ===
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...                       # Personal Access Token
DATABRICKS_CATALOG=your_catalog                # Unity Catalog name
DATABRICKS_SCHEMA=your_schema                  # Schema within catalog
GENIE_SPACE_ID=...                             # From Genie Space setup
VECTOR_SEARCH_INDEX=your_catalog.your_schema.ghana_facilities_index
VECTOR_SEARCH_ENDPOINT=ghana-medical-vs

# === LLM (fallback if Model Serving quota exceeded) ===
OPENAI_API_KEY=sk-...                          # Optional fallback
```

### requirements.txt

```
# Agent orchestration
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0

# Databricks SDK
databricks-sdk>=0.30.0
databricks-vectorsearch>=0.40
mlflow>=2.16.0

# Frontend
streamlit>=1.38.0
streamlit-folium>=0.22.0
folium>=0.17.0

# Data (local utilities)
pandas>=2.0.0
numpy>=1.24.0
python-dotenv>=1.0.0
```

### Project Structure

```
Hack-Nation/
├── AGENT.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   └── ghana_city_coords.json        # Static geocoding lookup (local)
├── src/
│   ├── app.py                        # Streamlit entry point
│   ├── config.py                     # Load .env, Databricks client init
│   ├── graph.py                      # LangGraph state graph definition (supervisor + nodes)
│   ├── state.py                      # Pydantic state schema for the agent graph
│   ├── nodes/
│   │   ├── supervisor.py             # Supervisor node — classifies intent, routes to agents
│   │   ├── sql_agent.py              # SQL Agent node — calls Databricks Genie
│   │   ├── rag_agent.py              # RAG Agent node — calls Databricks Vector Search
│   │   ├── medical_reasoning.py      # Medical Reasoning node — anomaly detection via Model Serving
│   │   ├── geospatial.py             # Geospatial node — Haversine, cold-spots (local)
│   │   └── synthesis.py              # Synthesis node — merges results, formats citations
│   ├── tools/
│   │   ├── genie_tool.py             # Databricks Genie SDK wrapper
│   │   ├── vector_search_tool.py     # Databricks Vector Search SDK wrapper
│   │   └── model_serving_tool.py     # Databricks Model Serving SDK wrapper
│   ├── databricks_clients.py         # Shared Databricks client initialization
│   └── map_component.py              # Folium map builder
└── notebooks/
    └── 01_setup_databricks.py        # Run once in Databricks: clean → upload → index → Genie
```

---

## Dataset Analysis (987 Rows)

### File: `Virtue_Foundation_Ghana_v0_3_-_Sheet1.csv`

- **987 rows** total: **920 facilities** + **67 NGOs**
- Download: https://drive.google.com/file/d/1qgmLHrJYu8TKY2UeQ-VFD4PQ_avPoZ3d/view

### Critical Data Issues (Handle in Notebook)

1. **NO LATITUDE/LONGITUDE** — Geocode from `address_city` using a static lookup table
2. **Sparse structured fields** — capacity (23 rows), numberDoctors (3 rows), area (2 rows)
3. **Dirty region names** — 53 variations for 16 regions. Normalize in notebook before upload
4. **71 duplicate facility names** — Deduplicate by name + city, merge parsed arrays
5. **Typo: "farmacy"** — Fix to "pharmacy" (5 records)
6. **Free-form fields are JSON strings** — Parse with `json.loads()` in notebook

### Column Coverage

| Field                 | Coverage | Notes |
| --------------------- | -------- | ----- |
| name                  | 100%     | |
| specialties           | 92%      | |
| capability            | 94%      | 784 have >0 items |
| procedure             | 79%      | 202 have >0 items |
| equipment             | 73%      | 91 have >0 items |
| address_city          | 94%      | |
| address_stateOrRegion | **26%**  | Very sparse — infer from city |
| facilityTypeId        | 73%      | |
| capacity              | **2%**   | Almost empty |
| numberDoctors         | **<1%**  | Almost empty |

### Free-Form Text Format

```json
["Performs emergency cesarean sections", "Offers hemodialysis treatment 3 times weekly"]
["Optical Coherence Tomography (OCT) machine", "Fundus photography equipment"]
["Emergency services operate 24/7", "Has 87 French and Ghanaian medical professionals"]
```

---

## Implementation — Milestone-Based

```mermaid
gantt
    title Hackathon Sprint
    dateFormat X
    axisFormat %s

    section Foundation — Databricks Setup
    Notebook: clean + geocode + upload to UC     :p1a, 0, 40
    Create Vector Search index                   :p1b, after p1a, 20
    Configure Genie Space                        :p1c, after p1b, 20

    section Core — LangGraph + Databricks Wiring
    LangGraph state + graph scaffold             :p2a, after p1c, 20
    Supervisor node + intent classification      :p2b, after p2a, 20
    SQL Agent node (Genie)                       :p2c, after p2b, 20
    RAG Agent node (Vector Search)               :p2d, after p2c, 20
    Medical Reasoning node (Model Serving)       :p2e, after p2d, 20
    Synthesis node + Streamlit wiring            :p2f, after p2e, 20

    section MVD Checkpoint
    Minimum Viable Demo MUST work                :milestone, crit, after p2f, 0

    section Surface — Map + Polish
    Folium map with facility markers             :p3a, after p2f, 30
    MLflow tracing decorators                    :p3b, after p3a, 20
    Citations + error handling                   :p3c, after p3b, 20

    section Stretch
    Geospatial cold-spots on map                 :p4a, after p3c, 30
    MLflow Tracing for citation trail            :p4b, after p4a, 30
    Planning dashboard                           :p4c, after p4b, 30
```

### Foundation — Databricks Setup (Notebook)

**Run `notebooks/01_setup_databricks.py` once in a Databricks notebook.** This does all data work on Databricks — no local data pipeline needed.

#### Step 1: Upload + Clean Data

Ref: [Unity Catalog — Managed Tables](https://docs.databricks.com/en/data-governance/unity-catalog/create-tables.html)

```python
import pandas as pd
from pyspark.sql import functions as F

# Upload CSV to a Volume, then read
df = spark.read.csv(
    "/Volumes/your_catalog/your_schema/data/ghana_facilities.csv",
    header=True, inferSchema=True
)

# Fix typo
df = df.withColumn("facilityTypeId",
    F.when(F.col("facilityTypeId") == "farmacy", "pharmacy")
     .otherwise(F.col("facilityTypeId")))

# Normalize region names
region_map = {
    "Greater Accra Region": "Greater Accra", "Accra": "Greater Accra",
    "ASHANTI": "Ashanti", "Ashanti Region": "Ashanti",
    "Western Region": "Western", "Central Region": "Central",
    # ... (full map in AGENT.md data section)
}
mapping_expr = F.create_map([F.lit(x) for kv in region_map.items() for x in kv])
df = df.withColumn("region_normalized", mapping_expr[F.col("address_stateOrRegion")])

# Save as managed Delta table
df.write.format("delta").mode("overwrite").saveAsTable("your_catalog.your_schema.ghana_facilities")
```

#### Step 2: Add Column Descriptions (Critical for Genie)

Ref: [ALTER TABLE — Column Comments](https://docs.databricks.com/en/sql/language-manual/sql-ref-syntax-ddl-alter-table.html)

```sql
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN name COMMENT 'Official name of healthcare facility or NGO';
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN procedure COMMENT 'JSON array of clinical procedures — surgeries, diagnostics, screenings';
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN equipment COMMENT 'JSON array of medical devices — MRI, CT, X-ray, surgical tools';
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN capability COMMENT 'JSON array of care levels — trauma levels, ICU, accreditations, staffing';
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN specialties COMMENT 'JSON array of camelCase medical specialties e.g. cardiology, ophthalmology';
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN facilityTypeId COMMENT 'Facility type: hospital, clinic, dentist, pharmacy, or doctor';
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN address_stateOrRegion COMMENT 'Ghana region (raw, may need normalization)';
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN region_normalized COMMENT 'Cleaned Ghana region name (one of 16 official regions)';
ALTER TABLE your_catalog.your_schema.ghana_facilities
  ALTER COLUMN address_city COMMENT 'City or town where the facility is located';
```

#### Step 3: Create Vector Search Index

Ref: [Mosaic AI Vector Search](https://docs.databricks.com/en/generative-ai/vector-search.html)

```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Create endpoint (one-time)
vsc.create_endpoint(name="ghana-medical-vs", endpoint_type="STANDARD")

# Create auto-embedding index over free-form text columns
vsc.create_delta_sync_index(
    endpoint_name="ghana-medical-vs",
    index_name="your_catalog.your_schema.ghana_facilities_index",
    source_table_name="your_catalog.your_schema.ghana_facilities",
    pipeline_type="TRIGGERED",
    primary_key="unique_id",
    embedding_source_columns=[
        {"name": "procedure", "model_endpoint_name": "databricks-gte-large-en"},
        {"name": "equipment", "model_endpoint_name": "databricks-gte-large-en"},
        {"name": "capability", "model_endpoint_name": "databricks-gte-large-en"},
    ],
    columns_to_sync=["name", "facilityTypeId", "address_city",
                     "region_normalized", "specialties", "description"]
)
```

#### Step 4: Configure Genie Space

Ref: [Databricks Genie](https://docs.databricks.com/en/genie/)

1. Databricks UI → **Genie** → **Create Genie Space**
2. Add table: `your_catalog.your_schema.ghana_facilities`
3. Add **custom instructions**:
   ```
   This dataset contains 987 healthcare facilities and NGOs in Ghana.
   The procedure/equipment/capability columns are JSON arrays of English strings.
   The specialties column contains JSON arrays of camelCase strings like "cardiology".
   Use LIKE '%keyword%' to search within JSON array columns.
   The region_normalized column has clean Ghana region names.
   ```
4. Add **example SQL queries**:
   ```sql
   -- How many hospitals have cardiology?
   SELECT COUNT(*) FROM ghana_facilities
   WHERE facilityTypeId = 'hospital' AND specialties LIKE '%cardiology%';

   -- Which region has the most hospitals?
   SELECT region_normalized, COUNT(*) as cnt FROM ghana_facilities
   WHERE facilityTypeId = 'hospital'
   GROUP BY region_normalized ORDER BY cnt DESC;

   -- Facilities with procedures but no equipment
   SELECT name, procedure, equipment FROM ghana_facilities
   WHERE procedure != '[]' AND (equipment = '[]' OR equipment IS NULL);
   ```
5. Note the **Genie Space ID** — needed in `.env`

---

### Core — LangGraph Agent Graph + Databricks Wiring

The local LangGraph graph orchestrates agent nodes. Each node calls a Databricks service via the SDK. MLflow traces every step. Ref: [LangGraph Docs](https://langchain-ai.github.io/langgraph/)

#### `src/config.py` — Databricks Client Setup

Ref: [Databricks SDK for Python](https://docs.databricks.com/en/dev-tools/sdk-python.html)

```python
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
import os

load_dotenv()

db_client = WorkspaceClient(
    host=os.getenv("DATABRICKS_HOST"),
    token=os.getenv("DATABRICKS_TOKEN")
)

GENIE_SPACE_ID = os.getenv("GENIE_SPACE_ID")
VS_INDEX = os.getenv("VECTOR_SEARCH_INDEX")
VS_ENDPOINT = os.getenv("VECTOR_SEARCH_ENDPOINT")
CATALOG = os.getenv("DATABRICKS_CATALOG")
SCHEMA = os.getenv("DATABRICKS_SCHEMA")
```

#### `src/tools/` — Databricks SDK Wrappers (LangGraph Tools)

Each tool wraps a Databricks service. Agents call these tools within LangGraph nodes.

**`src/tools/genie_tool.py`** — Text-to-SQL via Genie
```python
from src.config import db_client, GENIE_SPACE_ID

def query_genie(question: str) -> dict:
    """Send natural language to Genie, get SQL + results back.
    Ref: https://docs.databricks.com/en/genie/"""
    response = db_client.genie.start_conversation(
        space_id=GENIE_SPACE_ID,
        content=question
    )
    return {"sql": response.sql, "results": response.attachments}
```

**`src/tools/vector_search_tool.py`** — Semantic Search (RAG)
```python
from src.config import db_client, VS_INDEX

def query_vector_search(query_text: str, num_results: int = 10, filters: dict = None) -> list:
    """Semantic search over procedure/equipment/capability columns.
    Ref: https://docs.databricks.com/en/generative-ai/vector-search"""
    results = db_client.vector_search_indexes.query_index(
        index_name=VS_INDEX,
        columns=["name", "procedure", "equipment", "capability",
                 "address_city", "facilityTypeId", "specialties"],
        query_text=query_text,
        num_results=num_results,
        filters=filters
    )
    return results.data_array
```

**`src/tools/model_serving_tool.py`** — LLM Inference
```python
from src.config import db_client

def query_llm(system_prompt: str, user_message: str) -> str:
    """Call foundation model via Databricks Model Serving.
    Ref: https://docs.databricks.com/en/machine-learning/model-serving"""
    response = db_client.serving_endpoints.query(
        name="databricks-meta-llama-3-3-70b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )
    return response.choices[0].message.content
```

#### `src/state.py` — LangGraph State Schema

```python
from typing import TypedDict, Literal, Optional
from langgraph.graph import MessagesState

class AgentState(TypedDict):
    """Shared state passed between all LangGraph nodes.
    Ref: https://langchain-ai.github.io/langgraph/concepts/low_level/#state"""
    query: str                                          # Original user question
    intent: Literal["SQL", "SEARCH", "ANOMALY", "GEO"] # Classified by supervisor
    sql_result: Optional[dict]                          # From Genie
    search_result: Optional[list]                       # From Vector Search
    anomaly_result: Optional[str]                       # From Model Serving
    geo_result: Optional[dict]                          # From local geospatial
    final_answer: Optional[str]                         # Merged by synthesis node
    citations: list                                     # Audit trail for MLflow
```

#### `src/graph.py` — LangGraph State Graph Definition

```python
from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.nodes.supervisor import supervisor_node
from src.nodes.sql_agent import sql_agent_node
from src.nodes.rag_agent import rag_agent_node
from src.nodes.medical_reasoning import medical_reasoning_node
from src.nodes.geospatial import geospatial_node
from src.nodes.synthesis import synthesis_node
import mlflow

def route_by_intent(state: AgentState) -> str:
    """Conditional edge — routes to the right agent based on supervisor classification.
    Ref: https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges"""
    return state["intent"]

# Build the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("SQL", sql_agent_node)
workflow.add_node("SEARCH", rag_agent_node)
workflow.add_node("ANOMALY", medical_reasoning_node)
workflow.add_node("GEO", geospatial_node)
workflow.add_node("synthesis", synthesis_node)

# Edges: supervisor classifies intent → route to correct agent → merge in synthesis
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges("supervisor", route_by_intent,
    {"SQL": "SQL", "SEARCH": "SEARCH", "ANOMALY": "ANOMALY", "GEO": "GEO"})
workflow.add_edge("SQL", "synthesis")
workflow.add_edge("SEARCH", "synthesis")
workflow.add_edge("ANOMALY", "synthesis")
workflow.add_edge("GEO", "synthesis")
workflow.add_edge("synthesis", END)

# Compile
graph = workflow.compile()

@mlflow.trace
def run_agent(query: str) -> str:
    """Run the full agent graph. MLflow traces every step.
    Ref: https://docs.databricks.com/en/mlflow/llm-tracing"""
    result = graph.invoke({"query": query, "citations": []})
    return result["final_answer"]
```

#### `src/nodes/supervisor.py` — Intent Classification Node

```python
from src.tools.model_serving_tool import query_llm
from src.state import AgentState

ROUTER_PROMPT = """Classify this healthcare data question into ONE category:
- SQL: counts, aggregations, rankings, comparisons (e.g. "How many hospitals have cardiology?")
- SEARCH: specific facility services, capabilities, equipment (e.g. "What does Korle Bu offer?")
- ANOMALY: data inconsistencies, mismatches (e.g. "Facilities claiming surgery but lacking equipment?")
- GEO: distances, locations, medical deserts (e.g. "Hospitals within 50km of Tamale?")
Respond with ONLY the category name."""

def supervisor_node(state: AgentState) -> dict:
    """Supervisor node — classifies user intent using Databricks Model Serving LLM.
    Returns the intent label which drives conditional routing in the graph."""
    intent = query_llm(ROUTER_PROMPT, state["query"]).strip().upper()
    if intent not in ("SQL", "SEARCH", "ANOMALY", "GEO"):
        intent = "SQL"  # Default to Genie for unrecognized intents
    return {"intent": intent}
```

#### `src/nodes/sql_agent.py` — Genie Text-to-SQL Node

```python
from src.tools.genie_tool import query_genie
from src.state import AgentState

def sql_agent_node(state: AgentState) -> dict:
    """SQL Agent — sends the user question to Databricks Genie for Text-to-SQL.
    Genie generates SQL, executes it, and returns structured results."""
    result = query_genie(state["query"])
    return {"sql_result": result, "citations": state["citations"] + [{"source": "genie", "sql": result.get("sql")}]}
```

#### `src/nodes/rag_agent.py` — Vector Search RAG Node

```python
from src.tools.vector_search_tool import query_vector_search
from src.state import AgentState

def rag_agent_node(state: AgentState) -> dict:
    """RAG Agent — performs semantic search over facility free-form text using
    Databricks Mosaic AI Vector Search. Returns top-k matching facilities."""
    results = query_vector_search(state["query"])
    return {"search_result": results, "citations": state["citations"] + [{"source": "vector_search", "hits": len(results)}]}
```

#### `src/nodes/synthesis.py` — Result Merger + Citation Builder

```python
from src.tools.model_serving_tool import query_llm
from src.state import AgentState

SYNTHESIS_PROMPT = """Summarize this data into a clear, citation-backed answer.
Include facility names, regions, and specific data points. Format as markdown."""

def synthesis_node(state: AgentState) -> dict:
    """Synthesis node — merges results from whichever agent ran, formats a user-facing
    answer with citations, and logs the full trace via MLflow."""
    raw = state.get("sql_result") or state.get("search_result") or state.get("anomaly_result") or state.get("geo_result")
    answer = query_llm(SYNTHESIS_PROMPT, str(raw))
    return {"final_answer": answer}
```

#### `src/medical_reasoning.py` — Anomaly Detection Prompt

```python
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
```

#### `src/app.py` — Streamlit Frontend (calls LangGraph agent)

```python
import streamlit as st
from src.graph import run_agent
from src.map_component import create_ghana_map

st.set_page_config(page_title="Ghana Medical Intelligence Agent", layout="wide")
st.title("Ghana Medical Intelligence Agent")
st.caption("Bridging Medical Deserts — Powered by LangGraph + Databricks + MLflow")

with st.sidebar:
    st.header("Example Queries")
    for ex in [
        "How many hospitals have cardiology?",
        "What services does Korle Bu Teaching Hospital offer?",
        "Which facilities claim surgery but lack equipment?",
        "Show medical deserts for ophthalmology",
        "Where should the next mission go?",
    ]:
        if st.button(ex, key=ex):
            st.session_state.query = ex

col_chat, col_map = st.columns([1, 1])

with col_chat:
    query = st.text_input("Ask about healthcare facilities in Ghana:",
                          value=st.session_state.get("query", ""))
    if query:
        with st.spinner("Running agent graph..."):
            try:
                answer = run_agent(query)
                st.markdown(answer)
            except Exception as e:
                st.error(f"Something went wrong: {e}")

with col_map:
    st.subheader("Facility Map")
    # Render Folium map (see map_component.py)
```

---

### MVD Checkpoint (Minimum Viable Demo)

**Before moving to Surface, this must work:**

1. Databricks workspace has Delta table + Vector Search index + Genie Space
2. LangGraph graph compiles and runs end-to-end: supervisor → agent node → synthesis
3. Streamlit app calls `run_agent()` and returns answers for at least 3 of the 5 demo queries
4. Basic map renders with facility markers

**If this doesn't work, stop and debug the LangGraph graph + Databricks connection. Everything else is polish.**

---

### Surface — Map + MLflow + Polish

- Folium map with color-coded markers (hospital=blue, clinic=green, etc.)
- MLflow `@mlflow.trace` decorators on each agent node for step-level citation trail
- Basic `try/except` error handling on all Databricks SDK calls

### Stretch Goals — Clear Path Forward

| Stretch Goal | Technology | How to Add | Docs |
|---|---|---|---|
| **Geospatial cold-spots** | Local Python + Folium | Pre-compute at startup for common specialties, overlay red circles on Folium map | — |
| **Planning dashboard** | Streamlit | Add summary cards (flagged facilities, desert regions) above the chat | [docs.streamlit.io](https://docs.streamlit.io/) |
| **Composite queries** | LangGraph fan-out | Supervisor routes to multiple agent nodes in parallel (SQL + RAG), synthesis merges both | [langchain-ai.github.io/langgraph](https://langchain-ai.github.io/langgraph/) |
| **Mosaic AI Agent deploy** | Mosaic AI Agent Framework | Wrap the LangGraph graph as a `ChatAgent`, deploy on Databricks serving endpoint | [docs.databricks.com/en/generative-ai/agent-framework](https://docs.databricks.com/en/generative-ai/agent-framework/author-agent.html) |
| **LangGraph Studio** | LangGraph Platform | Visual debugger for the agent graph — step through nodes, inspect state | [langchain-ai.github.io/langgraph/concepts/langgraph_studio](https://langchain-ai.github.io/langgraph/concepts/langgraph_studio/) |

---

## Must-Have Queries (Official VF Question Bank)

| #   | Question                                                    | Agent Node → Databricks Tool | Priority  |
| --- | ----------------------------------------------------------- | --- | --------- |
| 1.1 | How many hospitals have cardiology?                         | SQL Agent → Genie | Must Have |
| 1.2 | How many hospitals in [region] can perform [procedure]?     | SQL Agent → Genie | Must Have |
| 1.3 | What services does [Facility Name] offer?                   | RAG Agent → Vector Search | Must Have |
| 1.4 | Are there clinics in [Area] that do [Service]?              | RAG Agent → Vector Search | Must Have |
| 1.5 | Which region has the most [Type] hospitals?                 | SQL Agent → Genie | Must Have |
| 2.1 | Hospitals treating [condition] within [X] km of [location]? | Geo Agent (local) + SQL Agent → Genie | Must Have |
| 2.3 | Largest geographic cold spots for [procedure]?              | Geo Agent (local) + SQL Agent → Genie | Must Have |
| 4.4 | Facilities claiming unrealistic procedures for their size?  | Medical Reasoning → Model Serving | Must Have |
| 4.7 | Correlations between facility characteristics?              | SQL Agent → Genie | Must Have |
| 4.8 | High procedure breadth with minimal equipment?              | Medical Reasoning → Model Serving | Must Have |
| 4.9 | Things that shouldn't move together?                        | Medical Reasoning → Model Serving | Must Have |
| 6.1 | Where is the workforce for [subspecialty] practicing?       | SQL Agent → Genie + Synthesis LLM | Must Have |
| 7.5 | Which procedures depend on very few facilities?             | SQL Agent → Genie | Must Have |
| 7.6 | Oversupply vs scarcity by complexity?                       | SQL Agent → Genie + Synthesis LLM | Must Have |
| 8.3 | Gaps where no organizations work despite evident need?      | Geo + SQL + Medical Reasoning (fan-out) | Must Have |

---

## Schema & Pydantic Models (From Dataset Creation Pipeline)

> These are the **exact** models used by the Virtue Foundation to extract the dataset. Understanding them is critical for interpreting the data.

### Organization Types

```python
class OrganizationExtractionOutput(BaseModel):
    ngos: Optional[List[str]]           # Non-profits delivering healthcare in low-income settings
    facilities: Optional[List[str]]     # Physical sites delivering in-person medical care
    other_organizations: Optional[List[str]]  # Entities that don't qualify as facility or NGO
```

### Facility Fields

```python
class Facility(BaseModel):
    name: str                              # Official name
    facilityTypeId: Literal["hospital", "pharmacy", "doctor", "clinic", "dentist"]
    operatorTypeId: Literal["public", "private"]
    affiliationTypeIds: List[Literal["faith-tradition", "philanthropy-legacy",
                                     "community", "academic", "government"]]
    description: str                       # Brief paragraph on services/history
    area: int                              # Floor area sqm (VERY SPARSE — 2 rows)
    numberDoctors: int                     # Doctor count (VERY SPARSE — 3 rows)
    capacity: int                          # Bed capacity (VERY SPARSE — 23 rows)
    # Address fields: address_city, address_stateOrRegion, address_country, etc.
    # Contact fields: phone_numbers, email, websites, officialWebsite, etc.
```

### Free-Form Text Columns (Core of IDP Challenge)

```python
class FacilityFacts(BaseModel):
    procedure: List[str]    # Clinical services — surgeries, diagnostics, screenings
    equipment: List[str]    # Medical devices — MRI, CT, X-ray, surgical tools, utilities
    capability: List[str]   # Care levels — trauma levels, ICU, accreditations, staffing, capacity
```

**Extraction rules:** Facts are declarative English statements traceable to source content. No generic knowledge. Empty arrays `[]` = no data found (valid signal, not missing data).

### Medical Specialties (case-sensitive camelCase)

```
internalMedicine, familyMedicine, pediatrics, cardiology, generalSurgery,
emergencyMedicine, gynecologyAndObstetrics, orthopedicSurgery, dentistry,
ophthalmology, otolaryngology, radiology, pathology, anesthesia,
criticalCareMedicine, nephrology, medicalOncology, infectiousDiseases,
physicalMedicineAndRehabilitation, hospiceAndPalliativeInternalMedicine,
neonatologyPerinatalMedicine, endocrinologyAndDiabetesAndMetabolism,
plasticSurgery, cardiacSurgery, geriatricsInternalMedicine, orthodontics
```

| Term in data | Maps to |
|---|---|
| "Hospital" (generic) | `internalMedicine` |
| "Clinic" (generic) | `familyMedicine` |
| "Emergency", "ER" | `emergencyMedicine` |
| "Surgery" (generic) | `generalSurgery` |
| "Eye", "Ophthalmic" | `ophthalmology` |
| "Cardiac Surgery" | `cardiacSurgery` |
| "Pediatric", "Children" | `pediatrics` |
| "Maternity", "Obstetric" | `gynecologyAndObstetrics` |
| "Trauma" | `criticalCareMedicine` |
| "Oncology", "Cancer" | `medicalOncology` |

---

## Anti-Patterns

1. **Don't rely on capacity/numberDoctors** — only 23 and 3 rows have these. Use procedure-equipment cross-referencing.
2. **Don't skip geocoding** — No lat/lon in data. City lookup table is required for the map.
3. **Don't treat `[]` as missing** — Empty array = "nothing found", which is useful signal.
4. **Don't ignore duplicates** — 71 names appear >1 time. Deduplicate in the notebook.
5. **Don't hardcode answers** — System must generalize to new queries.
6. **Don't build a custom SQL agent** — Use Genie. It already understands your column descriptions.
7. **Don't over-engineer LangGraph** — Start with linear routing (supervisor → one agent → synthesis). Add fan-out later as a stretch goal.

---

## Demo Script (5 Minutes)

| Time      | Action                                                        | Shows |
| --------- | ------------------------------------------------------------- | ----- |
| 0:00–1:00 | Problem statement + architecture (LangGraph + Databricks)     | Vision, social impact |
| 1:00–2:00 | Query: "What services does Korle Bu Teaching Hospital offer?" | RAG Agent → Vector Search |
| 2:00–3:00 | Query: "Which facilities claim surgery but lack equipment?"   | Medical Reasoning → Model Serving |
| 3:00–4:00 | Query: "Show medical deserts for ophthalmology"               | Geo Agent → Map overlay |
| 4:00–5:00 | Query: "Where should the next mission go?"                    | Fan-out → SQL + Geo + LLM synthesis |

**Closing line**: "Every data point we extract represents a patient who could receive care sooner."

---

## Resources

### Challenge
- **Dataset CSV**: https://drive.google.com/file/d/1qgmLHrJYu8TKY2UeQ-VFD4PQ_avPoZ3d/view
- **Schema Docs**: https://drive.google.com/file/d/1CvMTA2DtwZxa9-sBsw57idCkIlnrN32r/view
- **VF Agent Questions**: https://docs.google.com/document/d/1ETRk0KEcWUJExuhWKBQkw1Tq-D63Bdma1rPAwoaPiRI/edit
- **VFMatch Globe**: https://vfmatch.org/explore?appMode=globe
- **Databricks x VF Blog**: https://www.databricks.com/blog/elevating-global-health-databricks-and-virtue-foundation

### Databricks Documentation (Free Edition)
- **Free Edition Signup**: https://signup.databricks.com
- **Free Edition Overview**: https://docs.databricks.com/en/getting-started/free-edition.html
- **Free Edition Limitations**: https://docs.databricks.com/en/getting-started/free-edition-limitations.html
- **Unity Catalog**: https://docs.databricks.com/en/data-governance/unity-catalog/index.html
- **Genie (Text-to-SQL)**: https://docs.databricks.com/en/genie/index.html
- **Mosaic AI Vector Search**: https://docs.databricks.com/en/generative-ai/vector-search.html
- **Model Serving**: https://docs.databricks.com/en/machine-learning/model-serving/index.html
- **MLflow Tracing**: https://docs.databricks.com/en/mlflow/index.html
- **Agent Framework**: https://docs.databricks.com/en/generative-ai/agent-framework/author-agent.html
- **Databricks SDK for Python**: https://docs.databricks.com/en/dev-tools/sdk-python.html
- **Notebooks**: https://docs.databricks.com/en/notebooks/index.html
- **Personal Access Tokens**: https://docs.databricks.com/en/dev-tools/auth/pat.html

### Agent Orchestration
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **LangGraph Concepts — State Graphs**: https://langchain-ai.github.io/langgraph/concepts/low_level/
- **LangGraph Conditional Edges**: https://langchain-ai.github.io/langgraph/concepts/low_level/#conditional-edges
- **LangGraph + MLflow**: https://docs.databricks.com/en/mlflow/llm-tracing/langgraph-tracing.html

### Frontend
- **Streamlit Docs**: https://docs.streamlit.io/
- **Folium Docs**: https://python-visualization.github.io/folium/

---

## Risks

- **Daily compute quotas** — Do data upload + index creation EARLY. If exceeded, compute pauses until next day
- **No GPU access** — Fine-tuning not feasible. Use pre-built foundation models via Model Serving
- **Network latency** — Databricks API calls add ~200-500ms. Keep geospatial math local
- **Genie accuracy** — May generate wrong SQL. Add column descriptions and example queries to improve
- **LangGraph complexity** — Keep the graph simple (linear routing MVP). Fan-out is stretch only
- **Fallback** — If Databricks is down, swap `src/tools/` wrappers to use OpenAI + local DuckDB

---

## Definition of Done

### MVP (Must ship)

- [ ] Databricks workspace: Delta table in Unity Catalog with column descriptions
- [ ] Genie Space configured with instructions and example queries
- [ ] Vector Search index created over procedure/equipment/capability columns
- [ ] LangGraph state graph: supervisor → conditional routing → agent nodes → synthesis
- [ ] SQL Agent node calls Genie for structured queries
- [ ] RAG Agent node calls Vector Search for semantic queries
- [ ] Medical Reasoning node calls Model Serving for anomaly detection
- [ ] MLflow `@mlflow.trace` on `run_agent()` for citation trail
- [ ] Streamlit app calls `run_agent()` and displays results
- [ ] Folium map with color-coded facility markers
- [ ] Basic error handling (try/except on all Databricks SDK calls)
- [ ] 5 demo queries work end-to-end

### Stretch (if time permits)

- [ ] Geospatial agent node: cold-spot detection + medical desert overlay on map
- [ ] LangGraph fan-out: composite queries routing to multiple agents in parallel
- [ ] Planning dashboard with summary cards
- [ ] Mosaic AI Agent Framework deployment (LangGraph → ChatAgent → serving endpoint)
- [ ] LangGraph Studio for visual debugging
