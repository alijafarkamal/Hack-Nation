# Bridging Medical Deserts - Databricks Track

**Hack Nation 2026 - Virtue Foundation Ghana Medical Facility Analysis**

## ???? Mission

Build an Intelligent Document Parsing (IDP) Agent that extracts, verifies, and reasons over medical facility data from Ghana to identify **medical deserts** and infrastructure gaps.

## ???? Quick Start

```bash
# Install dependencies
pip install -r requirements.txt --break-system-packages

# Launch Streamlit UI
streamlit run streamlit_app.py
```

Opens at **http://localhost:8501**

## ???? Dataset

- **987 facilities** from Virtue Foundation Ghana v0.3
- **920 hospitals/clinics** + **67 NGOs**
- Free-form text fields: procedures, equipment, capabilities
- Challenge: No geocoordinates, sparse structured data

## ??????? Architecture

**Multi-Agent System:**

User Query ??? Supervisor ??? {SQL, Vector, Medical, Geo} ??? Synthesis ??? Response + Map

## ???? Current MVP Features

- ??? Medical Desert Detection
- ??? Anomaly Detection  
- ??? Facility Search (987 facilities)
- ??? Interactive Maps
- ??? Dashboard Analytics

## ???? Key Files

- **AGENT.md** - Complete instructions (MAIN DOC)
- **streamlit_app.py** - UI entry point
- **agents/** - Multi-agent system
- **data/raw/ghana/facilities_real.csv** - Dataset

## ???? Tech Stack (Lightweight)

- Streamlit + Folium + Plotly
- LangGraph (multi-agent)
- Pandas + DuckDB
- ChromaDB (local embeddings)
- sentence-transformers (no torch/openai)

See **AGENT.md** for complete details.
