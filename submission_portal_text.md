# Hackathon Portal Submission Text
Copy and paste these exact paragraphs into the Hackathon Submission Portal!

### 1. Problem & Challenge
In India, families often lose critical time trying to find a hospital that actually has the required capability (ICU, surgery, oxygen). The problem isn't just whether hospitals exist, but whether their listed capabilities are trustworthy. Facility records are often messy, incomplete, and contradictory. A hospital may claim advanced surgery but lack anesthesiologist evidence. This creates a dangerous "discovery-to-care" gap. Our challenge was converting 10,000+ fragmented healthcare records into verified, trust-scored facility intelligence.

### 2. Target Audience
The primary users are families, NGO field workers, and public-health planners. Families benefit by finding safe, verified facilities in emergencies. NGOs benefit by identifying underserved regions to deploy resources. Policymakers benefit from our district-level medical desert intelligence, which shows exactly where critical capabilities are missing or where facility data is dangerously unreliable.

### 3. Solution & Core Features
`care-india` is an agentic healthcare intelligence platform built on Databricks. 
**Core Features:**
- Natural-language semantic search via Databricks Vector Search.
- **LLM-as-a-Judge Validation:** A secondary AI layer that grades primary hospital recommendations for hallucinations.
- **Medical & Data Desert Detection:** Distinctly maps regions with 0 hospitals vs. regions where hospitals exist but lack transparent equipment data.
- **Data Readiness Desk:** A human-in-the-loop Corrections API that allows users to report bad facility data directly back to our Unity Catalog Lakebase.
- **Traceability:** MLflow-backed audit trails proving why a facility was recommended.

### 4. Unique Selling Proposition (USP)
Most hospital search tools act as simple directories that blindly trust whatever a hospital claims. `care-india` acts as an **Adversarial Verification Engine**. Instead of just listing hospitals, we use an LLM-as-a-Judge architecture to verify operational evidence (e.g., flagging an ICU claim if no ventilators are documented). We also differentiate between true "Medical Deserts" and "Data Deserts," providing a level of policy intelligence that standard chatbots simply cannot match.

### 5. Implementation & Technology
We implemented a split-screen Next.js/React web application featuring a beautiful `react-leaflet` (CartoDB) map interface. Our robust backend is a FastAPI python service orchestrating a **LangGraph Multi-Agent Pipeline** natively on Databricks.
**Key Tech Stack:**
- **Databricks Vector Search:** (`gte-large-en` embeddings) for semantic facility retrieval.
- **Databricks Model Serving:** (`meta-llama-3-3-70b-instruct`) for Agent orchestration and LLM Judge scoring.
- **Databricks Unity Catalog:** Delta tables acting as our Lakebase for storing facility data and human corrections.
- **MLflow 3:** For per-node execution tracing and observability.

### 6. Results & Impact
Our platform successfully processes over 10,000 messy facility records and transforms them into an actionable, highly-trusted public health dashboard. By enforcing our LLM-as-a-Judge validation layer, we drastically reduce the risk of referring patients to incapable hospitals. Furthermore, our Medical vs. Data Desert mapping empowers policymakers to allocate resources accurately across India's 36 states, improving equitable access to life-saving care.
