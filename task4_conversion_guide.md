# care-india: Migration Guide (Challenge 03 -> Challenge 04)

## Context for the AI Agent / Developer
You are tasked with upgrading the **care-india** project from its current state (Databricks Challenge 03: Serving a Nation) to the advanced requirements of **Databricks Challenge 04: Data Legend**.

**Current Architecture:**
- **Backend:** FastAPI, LangGraph (Multi-Agent StateGraph), Databricks Vector Search, Databricks Genie.
- **Frontend:** Streamlit.
- **Databricks Environment:** Unity Catalog (`hack_nation.india_medical`), Vector Search endpoint (`india-medical-vs`), and Foundation Model APIs (`databricks-meta-llama-3-1-70b-instruct`).

## Core Requirements for Challenge 04

To succeed in Challenge 04, the application must shift from a stateless chat/triage tool into a **persistent, enterprise-grade decision-making platform** focused on a specific workflow.

### 1. Framework Migration: React + Databricks Apps
The user wants a superior, "Good UI" using React instead of Streamlit.
*   **Action:** Replace the `frontend/` Streamlit code with a modern React application (using Vite or Next.js).
*   **Databricks Support:** Databricks Apps fully supports React and Node.js. You can use the official [Databricks AppKit SDK](https://github.com/databricks/appkit) or continue using the FastAPI backend to serve the React static build files.
*   **Deployment:** The final app must be deployed natively via **Databricks Apps** (using an `app.yaml` file), NOT Streamlit Community Cloud.

### 2. Lakebase Persistence (Crucial Requirement)
Challenge 04 requires that user actions (notes, overrides, shortlists) survive beyond a single session.
*   **Database Setup:** Create a new Delta Table in Unity Catalog (e.g., `hack_nation.india_medical.user_shortlists`).
*   **Backend Implementation:** Add CRUD endpoints to the FastAPI backend using `databricks-sql-connector`:
    *   `POST /shortlist/save`: Save a facility ID, session ID, and user notes.
    *   `GET /shortlist/{session_id}`: Retrieve saved facilities.
    *   `PUT /shortlist/update_note`: Allow the planner to override/edit trust scores locally.

### 3. Mission Track Focus: Referral Copilot
The UI must be streamlined to fit exactly one workflow from the rubric. We are choosing **Referral Copilot**.
*   **Workflow:** User enters location and care need -> Agent returns evidence-backed shortlist -> **User saves candidates to a persistent shortlist** -> User can add personal notes or override the system's trust assessment.

---

## Innovative Features & Add-ons (Stretch Goals)

To win the hackathon, implement these innovative features in the React UI and LangGraph backend:

### A. Agentic Traceability Panel (UI Innovation)
*   Instead of just showing a "Trust Score," build a slick side-panel in React that visualizes the **Chain of Thought**.
*   Use data from the MLflow trace to show exact receipts: "We extracted X from paragraph 2 -> Validator found contradiction Y -> Final Score Z."
*   *UI Implementation:* A collapsible stepper component for each recommended hospital.

### B. Dynamic Crisis Mapping (Geospatial Innovation)
*   Integrate a dynamic React map (e.g., using `react-leaflet` or `mapbox-gl`).
*   Overlay the agent's trust-weighted findings on the map. Use red pins for "Data Deserts" (places where hospitals exist but have low trust scores) and green pins for verified facilities.

### C. Self-Correction / "Watchlist" Alerts
*   If a user saves a hospital to their persistent "Lakebase" shortlist, but a background agent detects a contradiction in a newer dataset, surface an "Alert" badge in the React UI notifying the user that their saved hospital's capabilities are now flagged.

---

## Step-by-Step Implementation Plan for the Agent

1. **Bootstrap React:** Initialize a React frontend inside the `frontend/` directory using Tailwind CSS for premium styling.
2. **Setup Lakebase Backend:** Add the `/shortlist` routes in `backend_api/routes/referral.py` and write the SQL statements to interact with the Unity Catalog table.
3. **Connect React to FastAPI:** Write the API client in React to hit `/triage/analyze` and the new `/shortlist` endpoints.
4. **Build the Referral Copilot UI:** Create the main search dashboard, the interactive facility cards, and the "My Saved Shortlist" dashboard.
5. **Configure Databricks App:** Create the `app.yaml` file to define how Databricks will host the FastAPI server and React static assets.

*Remember: Every important output the app produces must trace back to the facility text that supports it.*
