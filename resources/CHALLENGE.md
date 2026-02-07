# Bridging Medical Deserts

**Building Intelligent Document Parsing Agents for the Virtue Foundation**
*Sponsored Track by Databricks*

---

## 1. Motivation / Goal to Achieve

**Motivation:** By 2030, the world will face a shortage of over 10 million healthcare workers — not because expertise doesn't exist, but because it is not intelligently coordinated. This is a planetary-scale systems failure and a moonshot opportunity for AI.

Rooted in a real-world challenge faced by the Virtue Foundation, this problem is not theoretical: skilled doctors remain disconnected from the hospitals and communities that urgently need them.

This challenge invites you to build an agentic AI intelligence layer for healthcare — a system that can reason, decide, and act to connect the right medical expertise with the right hospitals at the right moment.

You are not just building software. You are designing the coordination engine for global healthcare — turning data into action and multiplying human impact through AI.

**Ambitious Goal:** The goal of this challenge is nothing less than to reduce the time it takes for patients to receive lifesaving treatment by 100x using an agentic AI system.

You will build an Intelligent Document Parsing (IDP) agent that goes far beyond simple search. This agent will extract and verify medical facility capabilities from messy, unstructured data — and reason over it to understand where care truly exists and where it is missing.

Your system should be able to:
- Identify infrastructure gaps and medical deserts
- Detect incomplete or suspicious claims about hospital capabilities
- Map where critical expertise is available — and where lives are currently at risk due to lack of access

If successful, your AI agent becomes part of a new healthcare intelligence layer: one that helps route patients and doctors faster, guide investment to the right places, and enable organizations like the Virtue Foundation to act with unprecedented speed and precision.

At planetary scale, even small improvements in coordination mean millions of patients treated sooner — and countless lives saved.

## 2. Core Features (MVP)

1. **Unstructured Feature Extraction:** Process free-form text fields (e.g., procedure, equipment, and capability columns) to identify specific medical data.
2. **Intelligent Synthesis:** Combine unstructured insights with structured facility schemas to provide a comprehensive view of regional capabilities.
3. **Planning system:** Think creatively how you could include a planning system which is easily accessible and could get adopted across experience levels and age groups.

## 3. Stretch Goals (We know that you can do it!)

- **Citations:** Include row-level citations to indicate what data was used to support a claim by an agent.
  - **Bonus:** Provide citations at the agentic-step level (e.g., if your agent makes 5 sequential reasoning calls, demonstrate which specific data was used for each step).
  - **Hint:** Consider how experiment tracking tools can "trace" the inputs and outputs of internal agent loops to provide this level of transparency.
- **Visualize with a Map:** Create a map to demonstrate your conclusions visually.
  - Inspiration: [VFMatch Globe](https://vfmatch.org/explore?appMode=globe&viewState=8.261875521286015%2C28.8340078062746%2C1.4222445256432446)
- **Real-impact Bonus:** The Databricks team is collaborating with the VF team to ship an agent by June 7th.
  - [VF Agent Questions (real-world requirements)](https://docs.google.com/document/d/1ETRk0KEcWUJExuhWKBQkw1Tq-D63Bdma1rPAwoaPiRI/edit?tab=t.0#heading=h.dp75tt7nodhp)

## 4. Hints and Resources

**Primary Tech Stack:** Focus on RAG and Agentic workflows, which are top-tier use cases for AI in the medical industry. Here's what the classic base state might be:
- **Agentic orchestrator:** LangGraph, LlamaIndex, CrewAI
- **ML lifecycle:** MLflow
- **RAG:** Databricks, FAISS, LanceDB
- **Text2SQL:** Genie

**Environment:** The challenge is scoped for small amounts of high-impact medical data to ensure compatibility with the Databricks Free Edition.

**Datasets:** Real-world facility reports and medical notes from a single country provided by the Virtue Foundation.

### Resource Links

| Resource | Link |
|---|---|
| Virtue Foundation Ghana Dataset | https://drive.google.com/file/d/1qgmLHrJYu8TKY2UeQ-VFD4PQ_avPoZ3d/view |
| Schema Documentation | https://docs.google.com/document/d/1UDkH0WLmm3ppE3OpzSuZQC9_7w3HO1PupDLFVqzS_2g/edit?tab=t.0#heading=h.efyjxgdkfw8u |
| Prompts & Pydantic Models (zip) | https://drive.google.com/file/d/1CvMTA2DtwZxa9-sBsw57idCkIlnrN32r/view |
| Prompts & Pydantic Models (local) | See `resources/prompts_and_pydantic_models/` (committed to this repo) |
| VF Agent Questions ("questions being explored") | https://docs.google.com/document/d/1ETRk0KEcWUJExuhWKBQkw1Tq-D63Bdma1rPAwoaPiRI/edit?tab=t.0#heading=h.dp75tt7nodhp |
| VFMatch Globe ("map inspiration") | https://vfmatch.org/explore?appMode=globe&viewState=8.261875521286015%2C28.8340078062746%2C1.4222445256432446 |
| Databricks x VF Blog | https://www.databricks.com/blog/elevating-global-health-databricks-and-virtue-foundation |
| Databricks Free Edition Signup | https://signup.databricks.com |

## 5. Evaluation Criteria

| Criterion | Weight | What Wins |
|---|---|---|
| **Technical Accuracy** | **35%** | How reliably does the agent handle "Must Have" queries and detect anomalies in facility data? |
| **IDP Innovation** | **30%** | How well does the solution extract and synthesize information from unstructured "free-form" text? |
| **Social Impact** | **25%** | Does the prototype effectively identify "medical deserts" to aid in resource allocation? |
| **User Experience** | **10%** | Is the interface intuitive for non-technical NGO planners using natural language? |

## 6. Why It Matters

Every data point you extract represents a patient who could receive care sooner. By automating understanding from medical notes — the most critical AI agent use case in healthcare — hackers are creating the intelligence layer that can transform scarcity into coordinated action and bring lifesaving expertise to the world's most underserved regions.
