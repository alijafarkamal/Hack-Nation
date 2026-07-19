export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 300_000);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Request-Id": crypto.randomUUID(),
        ...(init?.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : typeof data.error === "string" ? data.error : "";
      throw new ApiError(detail || `Backend request failed with HTTP ${response.status}.`, response.status, path);
    }
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The backend took too long to respond. Check Databricks readiness and try again.", 0, path);
    }
    if (error instanceof TypeError) {
      throw new ApiError(`Cannot reach the CareCompass backend at ${API_BASE}. Start backend_api/main.py and verify /healthz.`, 0, path);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public path: string) {
    super(message);
    this.name = "ApiError";
  }
}

export const analyze = (symptomsText: string) => api<TriageResponse>("/triage/analyze", {
  method: "POST", body: JSON.stringify({ symptoms_text: symptomsText, metadata: {} }),
});
export const matchFacilities = (sessionId: string, stateHint: string, topK: number) => api<MatchResponse>("/triage/match_facilities", {
  method: "POST", body: JSON.stringify({ session_id: sessionId, state_hint: stateHint, top_k: topK }),
});
export const health = () => api<{ok:boolean; integrations?:Record<string, unknown>}>("/healthz");
export const policyDeserts = (specialty: string, level: "pin" | "state") =>
  api<Record<string, any>>(`/policy/deserts?specialty=${encodeURIComponent(specialty)}&level=${level}`);
export const pinRisk = (pinCode: string) =>
  api<Record<string, any>>(`/policy/pin-risk/${encodeURIComponent(pinCode)}`);
export const enrich = (facilityName: string, state: string) => api<Record<string, any>>("/enrichment/facility", {
  method: "POST", body: JSON.stringify({ facility_name: facilityName, district: "", state }),
});
export const referralPreview = (sessionId: string, facilityName: string, patientSummary: string, phone = "") => api<Record<string, any>>("/referral/preview", {
  method: "POST", body: JSON.stringify({ session_id: sessionId, to_facility: facilityName, patient_summary: patientSummary, to_phone: phone }),
});

export type TriageResponse = {
  session_id: string; capabilities_needed: string[]; red_flags: string[]; correlation_id?: string;
};
export type MatchResponse = Record<string, any> & {
  search_result?: Record<string, any>[]; trust_artifacts?: Record<string, any>;
  synthesis_artifacts?: Record<string, any>; citations?: Record<string, any>[]; final_answer?: string;
};
