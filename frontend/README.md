# CareCompass India — Streamlit UI

Calls the FastAPI backend only. No Databricks credentials in the browser.

## Local run

1. **Terminal A — API** (repo root)

   ```bash
   uvicorn backend_api.main:app --reload
   ```

2. **Terminal B — Streamlit**

   ```bash
   cd frontend
   pip install -r requirements.txt
   streamlit run app.py
   ```

   Set `CARECOMPASS_API_URL` if the API is not on `http://127.0.0.1:8000`.

## Environment

| Variable | Description |
|----------|-------------|
| `CARECOMPASS_API_URL` | Base URL of FastAPI, e.g. `https://your-api.onrender.com` |

## Deploy

- **Streamlit Community Cloud:** main file `frontend/app.py`, Python 3.11+, set `CARECOMPASS_API_URL` to your deployed API.
- **Backend API:** use [Render `render.yaml`](../render.yaml) or any host running `uvicorn backend_api.main:app`.
