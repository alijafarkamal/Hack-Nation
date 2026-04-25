# Backend integrations (Twilio, Tavily)

## Environment

| Variable | Required | Effect |
|----------|----------|--------|
| `TWILIO_ACCOUNT_SID` | For SMS | All three required for real send |
| `TWILIO_AUTH_TOKEN` | For SMS | |
| `TWILIO_FROM_NUMBER` | For SMS | E.164, SMS-capable Twilio number |
| `TAVILY_API_KEY` | For `/enrichment/*` | Tavily Search for contact/website heuristics |

### Twilio: which values to use

- For this backend, use the **Live credentials** on **Account → Keys & credentials**:
  - **Account SID** → `TWILIO_ACCOUNT_SID` (starts with `AC...`)
  - **Auth token** (Live) → `TWILIO_AUTH_TOKEN`
- **Do not** use the **API key** pair (`SK…` + secret) for the Python `twilio` SDK used here; that is a different auth model. The SDK expects Account SID + Auth Token.
- **Test credentials** (separate `AC...` + test token) can be used for sandboxed behavior per Twilio docs.
- You still need a **messaging-capable** phone number in E.164 for `TWILIO_FROM_NUMBER` (buy or verify in Twilio).

`GET /healthz` returns `integrations: { twilio, tavily }` with `configured: bool` (no secret values).

## Referral

- `POST /referral/preview` with optional `to_phone` (E.164, e.g. `+9198XXXXXXXX`).
- `POST /referral/send` with `preview_id` and optional `to_phone` override.
- If Twilio is not configured, or send fails, response `mode` is `mock` or `mock_fallback` and HTTP 200 with audit id.

## Enrichment

- `POST /enrichment/facility` / `POST /enrichment/batch`
- Returns **503** if `TAVILY_API_KEY` is missing (single-facility route).

Results include confidence and `citations` — web search is **heuristic**; verify before clinical or operational use.
