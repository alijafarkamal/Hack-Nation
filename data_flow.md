# Ghana Medical Intelligence Agent — Data Flow

## End-to-End Data Flow

### Stage 1: Data Ingestion and Preparation

```
Raw CSV (987 Ghana healthcare facilities)
  → Pandas: clean typos ("farmacy"→"pharmacy"), normalize regions, rename columns
  → Pandas: export as Parquet
  → Databricks Files API: upload to Unity Catalog Volume
  → SQL CREATE TABLE: stored as Delta table (with Change Data Feed enabled)
  → ALTER COLUMN COMMENT: add column descriptions (helps Genie understand the schema)
  → Databricks Vector Search: auto-sync Delta table → vector index
      (embedding model: databricks-gte-large-en, source column: description)
```

### Stage 2: User Query → Multi-Agent Routing

```
User types a question in Streamlit
  → LangGraph Supervisor Node
      → Step 1: LLM normalizes query (fix typos, grammar)
      → Step 2: LLM classifies intent into one of 5 routes
```

### Stage 3: Five Specialized Agent Nodes

- **SQL Agent** — Intent: SQL — Service: Databricks Genie (Text-to-SQL) — Natural language → SQL → query Delta table
- **RAG Agent** — Intent: SEARCH — Service: Databricks Vector Search — Semantic similarity search over facility descriptions
- **IDP Extraction** — Intent: EXTRACT — Service: Vector Search + Model Serving — Parse free-form text → structured JSON facts
- **Medical Reasoning** — Intent: ANOMALY — Service: Vector Search + Model Serving — Detect procedure-equipment gaps, capability inflation
- **Geospatial** — Intent: GEO — Service: SQL Warehouse + Haversine — Medical desert detection, radius search, coverage maps

### Stage 4: Synthesis and Output

```
Agent results (from any of the 5 nodes)
  → Synthesis Node: LLM cross-references structured vs unstructured data
  → Flags contradictions, confirms agreements, cites sources
  → Final markdown answer with citations
  → MLflow Tracing: full audit trail of every step
  → Streamlit: renders styled answer cards, charts, interactive map, PDF export
```

---

## Technology Stack

### Databricks Platform (core backend)

- **Unity Catalog** — Delta table storage with column descriptions
- **Genie** — Text-to-SQL (natural language → SQL queries)
- **Mosaic AI Vector Search** — Semantic search with `databricks-gte-large-en` embeddings
- **Model Serving** — LLM inference (Qwen 3 80B) for reasoning, extraction, synthesis

### Orchestration

- **LangGraph** — Multi-agent graph with supervisor routing + conditional edges
- **MLflow** — Per-step tracing and audit trail

### LLM Fallback

- **OpenRouter** (minimax-m2.1) — Fallback when Databricks Model Serving is unavailable

### Frontend

- **Streamlit** — Interactive web UI with 3 tabs (Agent Chat, Mission Planner, Map)
- **Folium + MarkerCluster** — Interactive map with 700+ geocoded facilities
- **Plotly** — Bar charts (by region) and pie charts (by type)
- **fpdf2** — PDF planning report export

### Data Processing

- **Pandas** — CSV/Parquet handling, cleaning
- **Haversine formula** — Distance calculations for medical desert detection
- **Static geocoding** — 150+ Ghana cities mapped to coordinates

---

## Key Technical Achievements

1. **5-way intelligent routing** — Supervisor LLM classifies intent and routes to the right specialized agent (not a one-size-fits-all approach)
2. **IDP Innovation** — Converts messy free-form text arrays into structured, comparable facts via LLM extraction
3. **3-layer anomaly detection** — Rule-based flags + LLM medical reasoning + cross-reference validation in synthesis
4. **Medical desert detection** — Algorithmic identification of regions lacking specific specialties, with geospatial Haversine radius search
5. **Graceful degradation** — Databricks → OpenRouter LLM fallback; Databricks SQL → local CSV fallback; app works even without cloud credentials
6. **Full audit trail** — MLflow tracing on every agent step for transparency and reproducibility
