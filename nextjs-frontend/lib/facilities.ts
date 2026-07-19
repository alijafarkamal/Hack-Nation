import type { MatchResponse } from "./api";

export type Facility = {
  id: string; name: string; state: string; city: string; pin: string; type: string;
  score: number; verdict: "VERIFIED" | "REVIEW" | "SUSPICIOUS"; flags: string[];
  capabilities: string[]; description: string; latitude?: number; longitude?: number;
  citations: Record<string, any>[];
};

const list = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map(String);
  if (typeof value !== "string" || !value.trim()) return [];
  try { const parsed = JSON.parse(value); return Array.isArray(parsed) ? parsed.map(String) : [value]; }
  catch { return value.split(",").map(x => x.trim()).filter(Boolean); }
};
const normalizedScore = (value: unknown) => {
  const raw = Number(value ?? .5); return Math.max(0, Math.min(1, raw > 1 ? raw / 100 : raw));
};

export function deriveFacilities(result: MatchResponse, requestedCapabilities: string[]): Facility[] {
  const search = Array.isArray(result.search_result) ? result.search_result : [];
  const trust = Array.isArray(result.trust_artifacts?.per_facility) ? result.trust_artifacts.per_facility : [];
  const evidence = Array.isArray(result.synthesis_artifacts?.evidence_table) ? result.synthesis_artifacts.evidence_table : [];
  const names = new Set<string>();
  search.forEach(x => x?.name && names.add(String(x.name)));
  trust.forEach(x => x?.facility && names.add(String(x.facility)));
  evidence.forEach(x => x?.facility && names.add(String(x.facility)));
  return [...names].map((name, index) => {
    const s = search.find(x => String(x?.name || "") === name) || {};
    const t = trust.find(x => String(x?.facility || "") === name) || {};
    const e = evidence.find(x => String(x?.facility || "") === name) || {};
    const score = normalizedScore(t.combined_trust_0_1 ?? s.trust_score);
    const verdictRaw = String(t.final_verdict || (score >= .65 ? "VERIFIED" : score < .35 ? "SUSPICIOUS" : "REVIEW"));
    const verdict = (["VERIFIED", "REVIEW", "SUSPICIOUS"].includes(verdictRaw) ? verdictRaw : "REVIEW") as Facility["verdict"];
    const capabilities = [...new Set([...list(s.specialties), ...list(s.capability), ...requestedCapabilities])].slice(0, 5);
    const lat = Number(s.latitude ?? s.lat); const lon = Number(s.longitude ?? s.lon);
    const flags: string[] = Array.isArray(t.all_flags)
      ? [...new Set<string>((t.all_flags as unknown[]).map(value => String(value)).filter(Boolean))]
      : [];
    return {
      id: String(s.unique_id || s.id || `${name}-${index}`), name,
      state: String(e.state || s.state_normalized || "Location not listed"),
      city: String(s.address_city || ""), pin: String(s.pin_code || e.pin_or_city || ""),
      type: String(e.facilityTypeId || s.facilityTypeId || "Healthcare facility"), score, verdict,
      flags, capabilities,
      description: String(e.notes || s.description || "Facility evidence is available in the result receipts."),
      latitude: Number.isFinite(lat) && lat !== 0 ? lat : undefined,
      longitude: Number.isFinite(lon) && lon !== 0 ? lon : undefined,
      citations: (Array.isArray(result.citations) ? result.citations : []).filter(c => !c?.facility || String(c.facility) === name).slice(0, 8),
    };
  });
}
