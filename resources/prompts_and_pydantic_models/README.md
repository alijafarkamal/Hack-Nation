# Sponsor Resources — Prompts & Pydantic Models

These files are provided by the **Virtue Foundation / Databricks** challenge sponsors. They define the exact extraction pipeline used to create the Ghana healthcare facility dataset.

## Files

| File | Purpose |
|---|---|
| `organization_extraction.py` | Classifies text entities into `facilities`, `ngos`, or `other_organizations`. Contains the system prompt and `OrganizationExtractionOutput` Pydantic model. |
| `facility_and_ngo_fields.py` | Defines structured fields for `Facility` and `NGO` models (name, address, contact, facility type, capacity, etc.). Contains the `ORGANIZATION_INFORMATION_SYSTEM_PROMPT` with address parsing rules. |
| `free_form.py` | Defines `FacilityFacts` model with `procedure`, `equipment`, and `capability` free-form text arrays. Contains the `FREE_FORM_SYSTEM_PROMPT` with extraction guidelines and examples. |
| `medical_specialties.py` | Defines `MedicalSpecialties` model and the `MEDICAL_SPECIALTIES_SYSTEM_PROMPT` with facility name parsing rules and terminology mapping (e.g., "Eye Center" → `ophthalmology`). |

## Why These Matter

- The **system prompts** show exactly how the dataset was created — critical for understanding data quirks
- The **Pydantic models** define the schema our agent must work with
- The **specialty mapping rules** are essential for the Medical Reasoning and RAG agents
- These files are **read-only reference** — do not modify them
