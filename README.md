# Medical Intelligence Agent

**Hack Nation: Bridging Medical Deserts** | Databricks Track

An Intelligent Document Parsing (IDP) agent that extracts, verifies, and reasons over medical facility data from Ghana to identify medical deserts and infrastructure gaps.

---

## Architecture

```
User Question
     |
     v
 Streamlit UI ──> LangGraph Agent Graph ──> Databricks Free Edition
  (local)          (local orchestration)      (remote services)
```

**LangGraph** orchestrates a multi-agent graph. Each agent node calls **Databricks** services (Genie, Vector Search, Model Serving). **MLflow** traces every step. **Streamlit** renders the frontend.

### Agent Nodes

| Node | Purpose | Databricks Service |
|------|---------|--------------------|
| **Supervisor** | Classifies intent, routes to correct agent | Model Serving (LLM) |
| **SQL Agent** | Structured queries (counts, aggregations) | Genie (Text-to-SQL) |
| **RAG Agent** | Semantic search over facility descriptions | Vector Search |
| **IDP Extraction** | Extracts structured facts from free-form text | Model Serving (LLM) |
| **Medical Reasoning** | Anomaly detection, plausibility checks | Model Serving (LLM) |
| **Geospatial** | Distance queries, medical desert detection | Local (Haversine) + SQL |
| **Synthesis** | Merges results into cited Markdown answer | Model Serving (LLM) |

---

## Prerequisites

- **Python 3.13+** (managed via `pyenv` — see `.python-version`)
- **Databricks Free Edition** account with:
  - A SQL Warehouse (auto-provisioned on Free Edition)
  - A Personal Access Token (PAT)
- **Git**

---

## Quick Start

### 1. Clone and set up Python environment

```bash
git clone https://github.com/alijafarkamal/Hack-Nation.git
cd Hack-Nation

# If using pyenv (recommended)
pyenv install 3.13.4
pyenv local 3.13.4

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Required — get these from your Databricks workspace
DATABRICKS_HOST=https://dbc-XXXXX.cloud.databricks.com
DATABRICKS_TOKEN=dapi...

# Set after running the setup script (Step 3)
DATABRICKS_CATALOG=hack_nation
DATABRICKS_SCHEMA=ghana_medical
GENIE_SPACE_ID=...
VECTOR_SEARCH_INDEX=hack_nation.ghana_medical.ghana_facilities_index
VECTOR_SEARCH_ENDPOINT=ghana-medical-vs

# MLflow — use your Databricks email
MLFLOW_EXPERIMENT_PATH=/Users/you@example.com/ghana-medical-agent
LLM_ENDPOINT=databricks-qwen3-next-80b-a3b-instruct
```

### 3. Run Databricks setup

This script creates the Unity Catalog objects, uploads/cleans the dataset, creates the Delta table, and provisions the Vector Search index:

```bash
python scripts/setup_databricks.py
```

**What it does:**
- Creates catalog `hack_nation`, schema `ghana_medical`, and a volume
- Cleans the CSV (fixes column names, typos, normalizes regions)
- Uploads cleaned data as Parquet and creates a Delta table (987 rows)
- Creates a Vector Search endpoint and auto-embedding index on the `description` column
- Writes discovered values back to `.env`

**After the script completes**, you need to manually create a Genie Space:
1. Go to your Databricks workspace
2. Navigate to **Genie** in the sidebar
3. Create a new Space pointing to `hack_nation.ghana_medical.ghana_facilities`
4. Copy the Space ID from the URL and add it to `.env` as `GENIE_SPACE_ID`

### 4. Run tests

```bash
# Unit tests (local math, no Databricks needed)
pytest tests/test_geospatial.py -v

# Integration tests (requires Databricks credentials)
pytest tests/test_config.py -v       # Connection check
pytest tests/test_tools.py -v        # Genie, Vector Search, Model Serving
pytest tests/test_graph.py -v        # Graph compiles + routes correctly

# End-to-end
pytest tests/test_e2e.py -v
```

### 5. Launch the app

```bash
streamlit run src/app.py
```

Opens at [http://localhost:8501](http://localhost:8501).

---

## Project Structure

```
Hack-Nation/
├── src/
│   ├── app.py                  # Streamlit frontend (3 tabs: Chat, Planner, Map)
│   ├── config.py               # Databricks client setup + env loading
│   ├── graph.py                # LangGraph state graph definition
│   ├── state.py                # Shared state schema (AgentState)
│   ├── map_component.py        # Folium map builder
│   ├── nodes/
│   │   ├── supervisor.py       # Intent classification + routing
│   │   ├── sql_agent.py        # Genie Text-to-SQL
│   │   ├── rag_agent.py        # Vector Search RAG
│   │   ├── idp_extraction.py   # Structured fact extraction from free-form text
│   │   ├── medical_reasoning.py# Anomaly detection + plausibility checks
│   │   ├── geospatial.py       # Haversine distance + medical desert detection
│   │   └── synthesis.py        # Cross-reference + format final answer
│   └── tools/
│       ├── genie_tool.py       # Databricks Genie SDK wrapper
│       ├── vector_search_tool.py # Databricks Vector Search SDK wrapper
│       └── model_serving_tool.py # Databricks Model Serving SDK wrapper
├── scripts/
│   └── setup_databricks.py     # Automated Databricks provisioning
├── data/
│   └── ghana_city_coords.json  # Static city geocoding lookup
├── resources/
│   ├── CHALLENGE.md            # Full challenge brief
│   └── Virtue Foundation Ghana v0.3 - Sheet1.csv  # Raw dataset (987 rows)
├── tests/                      # pytest test suite
├── AGENT.md                    # Detailed architecture + implementation plan
├── .env.example                # Environment variable template
├── .python-version             # pyenv Python version (3.13.4)
└── requirements.txt            # Python dependencies
```

---

## Example Queries

The agent handles 5 intent categories:

| Intent | Example Query |
|--------|--------------|
| **SQL** | "How many hospitals have cardiology?" |
| **SEARCH** | "What services does Korle Bu Teaching Hospital offer?" |
| **EXTRACT** | "Extract capabilities for Tamale Teaching Hospital" |
| **ANOMALY** | "Facilities claiming unrealistic procedures for their size?" |
| **GEO** | "Where are ophthalmology deserts in Ghana?" |

All 15 Must-Have queries from the official Virtue Foundation question bank are supported.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph 1.0 |
| LLM | Databricks Model Serving (Qwen3 Next 80B) |
| Text-to-SQL | Databricks Genie |
| RAG | Databricks Mosaic AI Vector Search |
| Data | Delta Lake on Unity Catalog |
| Tracing | MLflow 3.x (Databricks-hosted) |
| Frontend | Streamlit + Folium |
| Language | Python 3.13 |

---

## Development

### Creating a dev branch

```bash
git checkout -b dev/your-name
```

### Key files to know

- **`src/graph.py`** — The LangGraph state graph. Add new nodes here.
- **`src/nodes/supervisor.py`** — Intent classification prompt. Edit to add new intents.
- **`src/state.py`** — Shared state schema. Add new fields here when adding nodes.
- **`src/config.py`** — All Databricks clients initialized here. Import from this module.

### Adding a new agent node

1. Create `src/nodes/your_node.py` with a function `your_node(state: AgentState) -> dict`
2. Add the intent to `src/state.py` and `src/nodes/supervisor.py`
3. Register the node in `src/graph.py` (add_node + add_edge)
4. Add a test in `tests/`

---

## License

Hackathon project for Hack Nation 2026.
