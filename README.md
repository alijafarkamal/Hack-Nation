# CareCompass India: Multi-Agent Healthcare Intelligence & Policy Inference System

> **Advanced Agentic Clinical Decision Support and Geospatial Analysis for 1.4 Billion Lives**

CareCompass is a comprehensive, multi-agent AI system designed to resolve fragmented healthcare infrastructure data into trusted, evidence-backed clinical intelligence. By leveraging a sophisticated Retrieval-Augmented Generation (RAG) pipeline and LLM-as-a-Judge consensus mechanisms, the system identifies medical facilities, validates capabilities, and executes real-time public health policy analysis (e.g., detecting "Medical Deserts" vs. "Data Deserts").

---

## 🔬 System Architecture & Research Novelty

The core of CareCompass is built upon a **Directed Acyclic Graph (DAG) state-machine**, orchestrating specialized AI agents to execute parallel retrieval, critical synthesis, and rigorous trust validation.

### 1. Multi-Agent Orchestration (LangGraph)
The backend implements a sophisticated state graph architecture where distinct LLM agents possess isolated responsibilities. 
* **Triage Agent:** Analyzes unstructured clinical text to extract exact ICD-10 scale capabilities and emergency flags.
* **Retrieval Agent:** Interfaces with high-dimensional vector stores to extract localized hospital candidates using semantic similarity.
* **Synthesis Agent:** Cross-references retrieved facilities against clinical requirements, synthesizing the final medical pathway.

### 2. LLM-as-a-Judge Consensus & Trust Scoring
To mitigate hallucination risks inherent in Generative AI healthcare applications, CareCompass implements a strict validation layer:
* **Evidence Validation:** A secondary, isolated LLM acts as an adjudicator, algorithmically scoring the primary synthesis agent's output against the raw retrieved context.
* **Trust Score Calculation:** Generates an empirical `trust_score` (0-100%). Outputs scoring below the defined threshold are flagged as "Suspicious" or "Requires Human Review," preventing unverified clinical routing.

### 3. Geospatial Policy Inference (Deserts Detection)
The system transcends simple retrieval by acting as a public health policy analysis engine:
* **Medical Desert Identification:** Geographically correlates zip-code/district population demands against verified hospital capabilities. If 0 facilities are returned for a specialized capability (e.g., Level 1 Trauma), the system flags a true Medical Desert.
* **Data Desert Classification:** Differentiates between actual resource scarcity and data-sparsity. If facilities exist geographically but lack digitized evidence of capabilities, it classifies the zone as a Data Desert, triggering data readiness protocols.

### 4. Hybrid Semantic Retrieval (Vector Search)
Traditional Boolean healthcare databases fail at mapping colloquial symptoms to clinical resources. 
* **Continuous Embedding Space:** Translates natural language symptoms (e.g., "my chest hurts severely") into high-dimensional embeddings.
* **Similarity Search:** Queries the Unity Catalog Vector Database to map clinical semantics directly to facility capability text, bypassing rigid schema limitations.

---

## 🛠 Technical Implementation & Stack

| Component | Technical Implementation | Core Function |
|-----------|-------------------------|---------------|
| **Orchestration** | `LangGraph` StateGraph | Parallel agent execution & state management |
| **Inference Engine** | Databricks Model Serving | High-throughput LLM deployment (`Llama 3.3 70B`) |
| **Vector DB** | Databricks Vector Search | Approximate Nearest Neighbor (ANN) retrieval |
| **Data Storage** | Unity Catalog Delta Tables | ACID-compliant storage for facility master-data |
| **Backend REST** | FastAPI & Uvicorn | Asynchronous Python API and Static File Serving |
| **Frontend Runtime** | Next.js 14 (Static Export) | High-performance, edge-cacheable React UI |
| **Geospatial Engine** | `react-leaflet` (CartoDB) | Interactive visualization of policy deserts |

---

## 🚀 Execution & Deployment Pipeline

The project implements a decoupled-but-unified deployment architecture. The highly interactive Next.js application is compiled into a static export and served directly from the FastAPI Python server, allowing seamless Databricks Apps deployment.

### Backend Initialization (FastAPI)
```bash
# Initialize Python Virtual Environment & Dependencies
pip install -r requirements.txt
pip install "databricks-sql-connector>=4.0.0"

# Execute Asynchronous Server
uvicorn backend_api.main:app --reload --host 0.0.0.0 --port 8000
```
*Environment Requirements: Databricks Workspace Token, Host URL, and SQL HTTP Path configured in `.env`.*

### Frontend Compilation (Next.js)
```bash
cd nextjs-frontend

# Install dependencies and compile static UI
npm install
npm run build
```
*The Next.js configuration enforces `output: "export"` and `trailingSlash: true` to generate an `/out` directory, which is dynamically mounted by FastAPI's `StaticFiles` router.*

---

## 📊 Observability & Auditing
Every agentic decision, from initial capability extraction to final trust scoring, is logged using **MLflow 3**. 
* **Trace Propagation:** Correlation IDs are passed from the Next.js client through FastAPI middleware directly into the LangGraph state.
* **Audit Trails:** Enables researchers and clinical auditors to replay any agent's thought process, ensuring 100% transparency in the clinical decision support lifecycle.

---
*Developed as an advanced technical exploration in AI-driven healthcare informatics.*
