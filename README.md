# 🏥 Bridging Medical Deserts — Hack Nation 2026

**Databricks Track | Virtue Foundation Ghana Medical Facility Analysis**

---

## 🎯 Mission

Build an **Intelligent Document Parsing (IDP) Agent** that extracts, verifies, and reasons over medical facility data from Ghana (provided by the Virtue Foundation) to identify **medical deserts** and infrastructure gaps. The system parses unstructured free-form text, synthesizes it with structured facility schemas, detects anomalies, and presents findings through an interactive map + natural language interface.

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt --break-system-packages

# Launch Streamlit UI
streamlit run streamlit_app.py
```

Opens at **http://localhost:8501**

---

## 📊 Dataset

| Stat | Value |
|------|-------|
| **Total Facilities** | 987 rows |
| **Hospitals/Clinics** | 920 |
| **NGOs** | 67 |
| **Top City** | Accra (309 facilities) |
| **Regions Covered** | 16 Ghana regions |
| **Free-Form Fields** | procedure, equipment, capability (JSON arrays) |

### Data Challenges Handled

- **No geocoordinates** — geocoded from city names using a static Ghana city coordinate lookup
- **Dirty region names** — 53 variations normalized to Ghana's 16 official regions
- **71 duplicate facility names** — deduplicated by merging data from duplicate rows
- **Typos** — "farmacy" → "pharmacy" (5 records) auto-corrected on load
- **Sparse structured fields** — only 2% have bed counts, <1% have doctor counts

### Data Coverage

| Field | Coverage |
|-------|----------|
| Name | 100% |
| Specialties | 92% |
| Capabilities | 94% |
| Procedures | 79% |
| Equipment | 73% |
| City | 94% |
| Region | 26% (inferred from city when missing) |
| Description | 67% |

---

## 🏗 Architecture

### Multi-Agent System with Supervisor Router

```
User Query → Supervisor Agent → Fan-out to Sub-Agents → Synthesis → Response + Map
```

| Agent | Role | Tech |
|-------|------|------|
| **Orchestrator** | Intent classification & query routing | LangGraph |
| **Parser Agent** | Structured queries (counts, aggregations, filters) | DuckDB + LLM |
| **Verification Agent** | Cross-reference claims, detect anomalies | LLM reasoning |
| **Mapper Agent** | Distance calculations, cold-spot detection | Haversine formula |
| **Organization Extraction** | Extract org-level data from free-form text | Pydantic models |
| **Medical Specialties** | Specialty parsing and classification | LLM + schema |
| **Free Form** | Parse procedure/equipment/capability JSON arrays | IDP pipeline |
| **Facility & NGO Fields** | Structured field extraction | Pydantic models |

### Query Routing

| Query Pattern | Agents Used |
|---------------|-------------|
| "How many hospitals have X?" | Parser (SQL) only |
| "What services does [Facility] offer?" | Free Form + Parser |
| "Facilities claiming X but lacking Y?" | Parser → Verification |
| "Hospitals within X km treating Y?" | Parser + Mapper (parallel) |
| "Show medical deserts for X" | Parser → Mapper (cold-spots) |
| "Where should the next mission go?" | All agents → Synthesis |

---

## ✅ Features

- **Medical Desert Detection** — Grid-based cold-spot analysis across Ghana for any specialty
- **Anomaly Detection** — Procedure-equipment cross-referencing (e.g., claims surgery but no surgical equipment)
- **Facility Search** — Search all 987 facilities by name, city, region, specialty, or service
- **Interactive Maps** — Folium maps with color-coded facility markers and medical desert overlays
- **Dashboard Analytics** — Plotly charts for regional distribution, facility types, and data coverage
- **Natural Language Interface** — Ask questions in plain English, get cited answers

---

## 📂 Project Structure

```
├── streamlit_app.py                    # Streamlit UI entry point
├── agents/
│   ├── orchestrator.py                 # Supervisor agent — routes queries
│   ├── parser_agent.py                 # SQL/structured data queries
│   ├── verification_agent.py           # Anomaly detection & cross-referencing
│   ├── mapper_agent.py                 # Geospatial calculations & maps
│   ├── organization_extraction.py      # Organization-level data extraction
│   ├── medical_specialties.py          # Medical specialty classification
│   ├── free_form.py                    # Free-form text parsing (IDP)
│   └── facility_and_ngo_fields.py      # Structured field extraction
├── config/
│   └── settings.py                     # Environment vars & feature flags
├── utils/
│   ├── virtue_data_loader.py           # CSV loader with cleaning & geocoding
│   ├── databricks_vector_search.py     # Databricks Vector Search integration
│   ├── mlflow_tracing.py               # MLflow agent tracing for citations
│   └── unity_catalog.py                # Unity Catalog data upload
├── prompts_and_pydantic_models/        # LLM prompts & Pydantic schemas
├── data/
│   ├── raw/ghana/facilities_real.csv   # Raw dataset (987 rows)
│   └── schemas/facility_schema.json    # Facility data schema
├── notebooks/
│   └── 01_data_ingestion.py            # Data exploration notebook
└── requirements.txt                    # Python dependencies
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Streamlit + Folium + Plotly |
| **Agent Orchestration** | LangGraph |
| **Data** | Pandas + DuckDB |
| **Vector Search** | ChromaDB (local) / Databricks Vector Search |
| **LLM** | Databricks Model Serving / OpenAI GPT-4o |
| **Embeddings** | sentence-transformers / Databricks GTE-Large |
| **Tracing** | MLflow Tracing (citation trail) |
| **Geospatial** | Haversine formula + Ghana city coordinates |

---

## 📊 Evaluation Criteria

| Criterion | Weight | Focus |
|-----------|--------|-------|
| **Technical Accuracy** | 35% | Reliably handles must-have queries, detects anomalies |
| **IDP Innovation** | 30% | Extracts + synthesizes from unstructured free-form text |
| **Social Impact** | 25% | Identifies medical deserts, aids resource allocation |
| **User Experience** | 10% | Intuitive for non-technical NGO planners |

---

## 🎬 Demo Queries

1. **"How many hospitals have cardiology?"** — SQL aggregation
2. **"What services does Korle Bu Teaching Hospital offer?"** — Vector search + citations
3. **"Which facilities claim surgery but lack equipment?"** — Anomaly detection
4. **"Show medical deserts for ophthalmology"** — Map visualization + cold spots
5. **"Where should the next mission go?"** — Planning synthesis + recommendation

---

## 🔗 Resources

- [Dataset CSV](https://drive.google.com/file/d/1qgmLHrJYu8TKY2UeQ-VFD4PQ_avPoZ3d/view)
- [VF Agent Questions](https://docs.google.com/document/d/1ETRk0KEcWUJExuhWKBQkw1Tq-D63Bdma1rPAwoaPiRI/edit)
- [VFMatch Globe](https://vfmatch.org/explore?appMode=globe)
- [Databricks Free Edition](https://signup.databricks.com)

---

*"Every data point we extract represents a patient who could receive care sooner."*
