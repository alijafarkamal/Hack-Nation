# Frontend Architecture Instructions: "Data Legend" Hackathon

This document is for the Frontend Team building the React/Vite UI. Our backend has been upgraded with two critical innovative features to secure maximum points for the **"Evidence & Trust (35%)"** and **"Product Judgment (30%)"** criteria in Challenge 04.

## 1. Eliminate the Bloat
The judges want a focused **Referral Copilot** track. 
*   **Remove:** The "System Architecture", "Query Analytics", and any other unnecessary diagnostic tabs.
*   **Keep:** "Triage & Match" (the main copilot) and "Saved Shortlists" (the Lakebase integration).

## 2. Implement the "Data Desert" Warning Banner
The backend `/triage/match_facilities` endpoint now returns a new JSON field: `"desert_analysis"`.
*   If `desert_analysis` is not `null`, you **must** display it prominently as an Alert banner at the top of the search results.
*   **Why it wins:** It distinguishes a true Medical Desert (0 hospitals exist) from a Data Desert (hospitals exist but data is too sparse to prove they have ICUs). The judges explicitly requested this distinction.

## 3. The "Trust & Evidence" Modal (Traceability)
Do not just show a trust score number. For every facility card, add a **"View Evidence Receipts"** button.
*   This button should open a Modal displaying the MLflow reasoning trace.
*   Specifically, show what the Extractor Agent found in the raw text, and if the Validator Agent flagged any contradictions.

## 4. The Interactive Map (`react-leaflet`)
Since the backend returns facility coordinates (if available) and states:
*   Integrate a Leaflet map beside the results.
*   Drop pins for the recommended facilities.
*   **Innovation:** Color code the pins based on Trust Score (Green = Verified, Orange = Needs Review).

## 5. The "Data Readiness Desk" (New Feature!)
The challenge asks for a way for humans to review and clean up suspicious data. I built a new endpoint: `POST /corrections/submit`.
*   On every facility card, add a small link: `Report Incorrect Data`.
*   It should open a form asking the user to submit a correction (e.g., "This hospital closed its ICU in 2024").
*   Hit the `/corrections/submit` API, which will permanently log it into our Databricks Lakebase!
