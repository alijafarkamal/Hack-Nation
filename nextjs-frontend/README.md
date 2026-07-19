# CareCompass Next.js frontend

Separate high-fidelity frontend for the existing CareCompass FastAPI backend. The original Streamlit application in `frontend/` is unchanged.

## Run

Start the backend from the repository root:

```powershell
python backend_api\main.py
```

Then open another terminal:

```powershell
cd nextjs-frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

The page uses only existing endpoints: triage analysis, facility matching, health, Tavily enrichment, and referral preview. Trust percentages describe evidence consistency, not accreditation. Capability labels are recorded dataset claims, not real-time availability.
