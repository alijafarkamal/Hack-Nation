const BASE = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? '/api' : '')

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', 'X-Request-Id': crypto.randomUUID(), ...(init?.headers || {}) }
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || body.error || `Request failed (${response.status})`)
  return body as T
}

export const analyze = (symptoms_text: string) => api<any>('/triage/analyze', { method: 'POST', body: JSON.stringify({ symptoms_text }) })
export const match = (session_id: string, state_hint: string, top_k = 8) => api<any>('/triage/match_facilities', { method: 'POST', body: JSON.stringify({ session_id, state_hint, top_k }) })
export const getShortlist = (session: string) => api<any>(`/shortlist/${encodeURIComponent(session)}`)
export const saveFacility = (payload: any) => api<any>('/shortlist/save', { method: 'POST', body: JSON.stringify(payload) })
export const updateFacility = (payload: any) => api<any>('/shortlist/update_note', { method: 'PUT', body: JSON.stringify(payload) })
