# Frontend Architecture Instructions: "Data Legend" Hackathon

This document is for the Frontend Team building the React/Vite UI. Our backend has been upgraded with two critical innovative features to secure maximum points for the **"Evidence & Trust (35%)"** and **"Product Judgment (30%)"** criteria in Challenge 04.

## 1. Eliminate the Bloat (The 2-Tab Layout)
The judges want a focused **Referral Copilot** track. 
Please look at the 1st place project from last year (Veri Care). They ONLY used two tabs:
*   **Tab 1: Pulse (Chat + Map)**: A split-screen UI. 30% on the left is the chatbot/search interface. 70% on the right is the full-screen map.
*   **Tab 2: Analytics (Deserts)**: A full-screen map showing Medical Deserts.
*   **Remove:** The "System Architecture", "Query Analytics", and any other unnecessary diagnostic tabs from our old code.

## 2. Map Configuration (Leaflet + CartoDB)
Do not use Google Maps. Do not use standard OpenStreetMap tiles (they look cluttered).
*   Use **`react-leaflet`**.
*   Set the Map Tile Layer URL to **CartoDB Positron**:
    `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png`
*   This will give you the beautiful, clean, light-grey aesthetic that the 1st place project used.

## 3. The "LLM-as-a-Judge" Output Validator (NEW!)
The backend `/triage/match_facilities` endpoint now returns a new JSON object: `"llm_judge"`.
```json
"llm_judge": {
  "trust_score": 85,
  "judge_note": "The AI correctly identified hospitals in Bihar, but one hospital lacks explicit ICU data."
}
```
*   **How to display it:** At the very bottom of every AI chat response in the left sidebar, add a tiny box that says: `"Validated by Llama 3.3 - Trust Score: {trust_score}%"`. 
*   Add a small tooltip or expanding text box that shows the `judge_note`. This proves to the judges that we have a secondary AI grading our main AI for safety!

## 4. Implement the "Data Desert" Warning Banner
The backend `/triage/match_facilities` endpoint now returns a new JSON field: `"desert_analysis"`.
*   If `desert_analysis` is not `null`, you **must** display it prominently as an Alert banner at the top of the search results or over the map.
*   It distinguishes a true Medical Desert (0 hospitals exist) from a Data Desert (hospitals exist but data is too sparse to prove they have ICUs).

## 5. The "Trust & Evidence" Modal (Traceability)
Do not just show a trust score number. For every facility card, add a **"View Evidence Receipts"** button.
*   This button should open a Modal displaying the MLflow reasoning trace.
*   Specifically, show what the Extractor Agent found in the raw text, and if the Validator Agent flagged any contradictions.
*   Add badges to the cards based on the `system_verdict`: "Safe to Refer" (Green), "Call Before Referral" (Yellow), "Do Not Refer" (Red).

## 6. The "Data Readiness Desk" (New Feature!)
The challenge asks for a way for humans to review and clean up suspicious data. I built a new endpoint: `POST /corrections/submit`.
*   On every facility card, add a small link: `Report Incorrect Data`.
*   It should open a form asking the user to submit a correction.
*   Hit the `/corrections/submit` API, which will permanently log it into our Databricks Lakebase!
