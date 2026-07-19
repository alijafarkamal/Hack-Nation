# care-india — Technical Slide Deck Source
> Paste this file into Gamma / Claude Slides / Pitch.com. Each `## SLIDE` heading is one slide.

---

## SLIDE 1 — Headline + GitHub

**care-india**
*Turning messy Indian healthcare records into trusted, evidence-backed care intelligence.*

**The core problem India faces:**
India has ~10,000+ facilities with severely uneven data quality — free-form text descriptions, missing geolocation, inconsistent capability fields. Planners cannot answer "Where is the nearest ICU in Bihar?" without a pipeline that understands messy text, cross-references claims, and quantifies uncertainty.

care-india solves this with an LLM-as-a-Judge Databricks backend that scores facility trustworthiness, maps healthcare deserts, and accepts human corrections into Lakebase.

---

## SLIDE 2 — System Architecture

**LangGraph Multi-Agent Pipeline on Databricks**

- **Primary Routing:** Supervisor intent classification
- **Semantic Search:** Databricks Vector Search pulls records containing exact `latitude` and `longitude`.
- **Output Validation (LLM Judge):** A secondary pass via `query_llm` grades the primary AI output for hallucinations, generating a 0-100 `trust_score` and `judge_note`.
- **Lakebase Persistence:** A `/corrections/submit` API writes human-verified corrections directly to a Databricks Delta table via `databricks-sql-connector`.

---

## SLIDE 3 — The "Truth Gap" & LLM-as-a-Judge

**How we verify facility claims:**
Most hospital search tools list facilities based on claimed services. care-india verifies those claims. 

**The Verification Engine:**
1. **Extractor:** Pulls bullet facts grounded only in the record.
2. **Validator:** Cross-references claims against medical-operations sanity (e.g., Surgery needs an OT).
3. **LLM Output Judge:** Grades the final API response before rendering it to the user.

If a hospital claims to have an ICU but mentions no ventilators, the AI flags it. The UI translates this into actionable badges: **Safe to Refer**, **Call Before Referral**, or **Do Not Refer Without Verification**.

---

## SLIDE 4 — Data Deserts vs. Medical Deserts

**Not all empty maps are the same.**
If a user searches for emergency surgery in Bihar and gets 0 results, the system automatically triggers a Databricks SQL fallback query:
- **Medical Desert:** There are literally 0 registered hospitals in the region.
- **Data Desert:** There are 400+ hospitals in the region, but their documentation is too sparse to prove they have the required equipment.

This distinction is surfaced to the frontend as a `desert_analysis` banner, providing critical intelligence to public health planners.

---

## SLIDE 5 — The 2-Tab Frontend & CartoDB Maps

**Extreme simplicity combined with extreme trust.**
We discarded bloated analytics dashboards in favor of a clean, split-screen UI built in React.

- **Tab 1 (Pulse):** A 30% width Chatbot side-panel beside a 70% width `react-leaflet` map. 
- **Tab 2 (Analytics):** A full-screen desert visualization map.
- **CartoDB Positron:** We use a custom light-grey basemap tile layer to ensure the UI looks premium and uncluttered.
- **Traceability Modals:** Clicking any facility on the map opens an MLflow evidence trace, showing exactly *why* the AI trusted it.

---

## SLIDE 6 — 60-second Demo Script + Stack Summary

**Live demo flow (60 seconds):**
1. **0:00-0:15:** Click "Emergency surgery in Bihar" quick-prompt. The AI returns facilities.
2. **0:15-0:30:** Show the LLM Judge score (e.g., 85/100) at the bottom of the chat.
3. **0:30-0:45:** Trigger a search that yields 0 results and highlight the "Data Desert" warning banner.
4. **0:45-0:60:** Click "Report Incorrect Data" on a facility card to demonstrate the Lakebase Corrections API syncing data back to Databricks.

**Complete Stack:** React, Leaflet, FastAPI, LangGraph, Databricks Vector Search, Databricks Unity Catalog, Llama 3.3.
