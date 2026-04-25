# Hack-Nation Reverse Engineering Playbook (From Medical-Intelligence-Agent)

## Purpose

This playbook distills the winning execution pattern from your previous project into a reusable system for future hackathons with similar judging criteria, even when the domain/company/data changes.

It is based on:
- `AGENT.md`
- `README.md`
- `data_flow.md`
- `resources/CHALLENGE.md`
- `resources/prompts_and_pydantic_models/README.md`

Reference repo: [Medical-Intelligence-Agent](https://github.com/alijafarkamal/Medical-Intelligence-Agent)

---

## What Made The Previous Project Win

### 1) You optimized directly for the rubric
- Architecture and implementation mapped 1:1 to score buckets (Technical Accuracy, IDP Innovation, Social Impact, UX).
- Each major feature had explicit value to judges, not just engineering elegance.

### 2) You built "proof-heavy" engineering
- Not just answers: citations, anomaly reasoning, cross-referencing, and map evidence.
- Demo showed why results were trustworthy, not only that they looked good.

### 3) You used staged delivery under time pressure
- Foundation -> Core -> MVD Gate -> Surface -> Stretch.
- This prevented polish-first failure and guaranteed a demoable product early.

### 4) You chose a strong agent shape
- Supervisor routing + specialized nodes + synthesis node.
- This is easy to explain, easy to debug, and naturally supports future extension.

### 5) You balanced cloud power with local reliability
- Cloud services handled heavy intelligence.
- Local logic handled deterministic tasks (geo math, fallbacks, rendering) for robustness.

---

## Reusable Architecture Template (Any Domain)

Use this same pattern for future hackathons:

1. **Supervisor Node**
   - Classify user query into intent categories.
2. **Specialized Nodes**
   - Structured query node (SQL/warehouse/BI agent).
   - Semantic retrieval node (RAG/vector search).
   - Extraction node (unstructured -> structured facts).
   - Reasoning node (anomaly/consistency checks).
   - Geospatial/planning/optimization node (domain-specific local logic).
3. **Synthesis Node**
   - Merge outputs, cross-check structured vs unstructured evidence.
   - Return citation-backed final answer.
4. **Frontend with Planner View**
   - Chat + map/visual + "action planning" tab for decision-makers.

This is judge-friendly because it shows clear intelligence decomposition and practical usability.

---

## Universal 24-Hour Execution Plan

## Phase 0 (Hour 0-1): Judge Alignment
- Extract evaluation criteria and weightings from challenge docs.
- Create "feature -> score impact" table before writing code.
- Define 5 demo queries that each prove a scoring area.

## Phase 1 (Hour 1-6): Foundation
- Ingest and clean data.
- Normalize key categorical fields.
- Handle duplicates and malformed free-form fields.
- Create storage/indexing layer.
- Add schema descriptions/comments to improve agent query quality.

## Phase 2 (Hour 6-12): Core Agent Graph
- Implement state schema.
- Add supervisor intent routing.
- Implement 3-5 specialized nodes (start minimal, stable).
- Implement synthesis node.
- Wire all into one runnable graph API.

## Phase 2.5 (Hour 12): MVD Gate (Non-Negotiable)
- Stop and run 5 critical end-to-end demo queries.
- Require at least 3/5 successful useful answers before continuing.
- If gate fails: fix routing/tool contracts immediately.

## Phase 3 (Hour 12-20): Surface + Impact
- Add map and planning panel.
- Add anomaly/coverage visual signals.
- Add evidence/citations in outputs.
- Add simple exports or summary cards for decision support.

## Phase 4 (Hour 20-24): Demo Hardening
- Smoke tests and recovery paths.
- Improve prompts and output formatting.
- Script 5-minute narrative demo timed by minute.
- Pre-compute expensive queries before live demo.

---

## Reverse-Engineered Deliverables Checklist

Use this exact list for future events:

- `AGENT.md` with mission, rubric mapping, architecture diagram, milestones.
- `README.md` with quickstart + prerequisites + runbook.
- `data_flow.md` with end-to-end pipeline from raw data to UI output.
- `src/state.py` with strict shared state contract.
- `src/graph.py` with explicit routing and compile/run entrypoint.
- `src/nodes/*` for each specialized function.
- `src/tools/*` wrappers around external services.
- `tests/` split into:
  - connectivity smoke tests
  - graph/routing tests
  - node contract tests
  - local deterministic math tests
  - end-to-end demo query tests
- `scripts/setup_*` for one-shot infra/data setup.

---

## Why `AGENT.md` Was So Powerful (And How To Reproduce It)

Your `AGENT.md` worked as:
- architecture spec,
- execution plan,
- judging strategy,
- demo script,
- risk register,
- and definition-of-done in one place.

For upcoming hackathons, always include these sections in `AGENT.md`:
1. Mission statement in challenge language.
2. Weighted evaluation table + what wins each bucket.
3. Architecture mapping to sponsor tools.
4. "What runs where" (local vs cloud).
5. Data quality issues and corrective rules.
6. Milestone gantt/timeline.
7. Must-have query bank mapped to node/tool.
8. Anti-patterns ("do not do" list).
9. 5-minute timed demo script.
10. Phase-based definition of done + test gates.

This document alone massively increases execution speed under pressure.

---

## Generalized Prompt/Model Strategy

From your winning approach:
- Use one LLM prompt for **routing**.
- Use one focused prompt for **extraction** (strict JSON schema).
- Use one focused prompt for **reasoning/anomaly checks**.
- Use one focused prompt for **synthesis** (citation-backed markdown).

Prompt design rules:
- Give strict output formats.
- Define contradiction rules explicitly.
- Treat empty arrays/fields as meaningful signals (not always missing).
- Separate extraction from synthesis (do not combine everything in one step).

---

## Tech Stack Contribution And Next-Hackathon Stack

## How the old tech stack helped you win

- **LangGraph**: gave clear multi-agent routing, which improved technical accuracy and made architecture easy to explain to judges.
- **Databricks Genie (Text-to-SQL)**: delivered structured query capability fast, without spending hackathon time building a fragile SQL agent.
- **Databricks Vector Search**: made semantic retrieval over messy text reliable, enabling strong IDP behavior beyond exact keyword matching.
- **Databricks Model Serving**: powered routing, extraction, reasoning, and synthesis with one consistent LLM backend.
- **MLflow tracing**: created an audit/citation story that boosted trust and made your outputs look production-minded.
- **Streamlit + Folium**: converted backend intelligence into judge-visible social-impact visuals (map + planning UX), not just terminal outputs.
- **Python local utilities (pandas/numpy/haversine)**: handled deterministic logic locally for speed, control, and resilience when cloud calls were slow.

## Recommended default stack for next hackathon

Use this unless sponsor constraints force alternatives:

- **Language/runtime**: Python 3.12+ (or challenge-required version)
- **Agent orchestration**: LangGraph
- **LLM backend**: sponsor-native model serving first; OpenAI/OpenRouter fallback
- **Structured analytics**: sponsor Text-to-SQL product (or warehouse SQL + thin tool wrapper)
- **Semantic retrieval**: sponsor vector search if available; else FAISS/LanceDB/Chroma
- **Data layer**: Delta/Postgres/DuckDB based on challenge scale and time budget
- **Tracing/observability**: MLflow (or LangSmith if team familiarity is higher)
- **Frontend**: Streamlit for 24-hour speed; optional React only if team already has a scaffold
- **Maps/geo**: Folium/Kepler/Mapbox depending on judging emphasis on geography
- **Testing**: pytest with smoke + routing + e2e gate tests

## Stack selection rule in first 30 minutes

Choose technologies that maximize:
1. **Judge-visible impact per hour**,
2. **integration reliability under time pressure**,
3. **explainability in a 5-minute demo**.

If a tool is powerful but slow to integrate, it is usually a bad hackathon choice.

---

## Judge-Surprise Multipliers (High ROI)

These gave high perceived sophistication for low extra effort:
- Citation trail for claims.
- Clear contradiction detection ("claims X but missing evidence Y").
- Planning tab with red/yellow/green priority tiers.
- Medical desert/coverage overlays (or domain equivalent).
- Graceful fallback behavior when cloud services degrade.

---

## What To Change For A Different Company/Challenge

Keep fixed:
- agent graph shape,
- execution phases,
- demo script style,
- test gate strategy.

Swap per challenge:
- taxonomy/schema,
- anomaly rules,
- planning heuristics,
- map/visual layer semantics,
- must-have question set.

Think of it as a reusable "competition operating system" with domain plugins.

---

## My Observation On Your Previous Project

This was not just a good prototype; it was a strong competition system design.

Most teams either:
- build a flashy UI without rigorous evidence, or
- build backend logic without decision-friendly UX.

Your project connected both: **credible intelligence + planner-ready interface + strong narrative alignment with social impact**. That combination is exactly what judges reward.

For the next hackathon, if you replicate this execution discipline and adapt the domain modules quickly, you can absolutely produce another top-tier result within 24 hours.

---

## Next Step Starter (For This Repo)

When you are ready, create these first:
- `AGENT.md` (new challenge version)
- `README.md` (quickstart and setup)
- `data_flow.md` (new domain pipeline)
- `src/` scaffold with `graph.py`, `state.py`, `nodes/`, `tools/`
- `tests/` with the same phase gates

Then we immediately implement the MVD route and lock the first 3/5 demo queries.
