"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Bookmark, Check, ChevronDown, CircleGauge, ClipboardPlus, Compass, Database, Filter, HeartPulse, Hospital, LayoutDashboard, List, LoaderCircle, MapPin, Pencil, Phone, Search, Send, ShieldCheck, Sparkles, X, Bell } from "lucide-react";
import { analyze, enrich, health, matchFacilities, referralPreview, submitCorrection, type MatchResponse, type TriageResponse } from "@/lib/api";
import { deriveFacilities, type Facility } from "@/lib/facilities";
import ThemeToggle from "./ThemeToggle";

const MapPanel = dynamic(() => import("./MapPanel"), { ssr: false });

const ILLUSTRATIVE_HOSPITAL_IMAGES = [
  "https://images.unsplash.com/photo-1764885517847-79d62138cc58?auto=format&fit=crop&w=640&q=78",
  "https://images.unsplash.com/photo-1538108149393-fbbd81895907?auto=format&fit=crop&w=640&q=78",
  "https://images.unsplash.com/photo-1586773860418-d37222d8fce3?auto=format&fit=crop&w=640&q=78",
  "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=640&q=78",
  "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=640&q=78",
];

const STATES = ["Andaman and Nicobar Islands","Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chandigarh","Chhattisgarh","Dadra and Nagar Haveli and Daman and Diu","Delhi","Goa","Gujarat","Haryana","Himachal Pradesh","Jammu and Kashmir","Jharkhand","Karnataka","Kerala","Ladakh","Lakshadweep","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Puducherry","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal"];

const label = (s: string) => s.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]/g, " ").replace(/\b\w/g, c => c.toUpperCase());

// Agent pipeline steps shown during processing
const AGENT_STEPS = [
  { icon: "🧠", label: "Supervisor Agent", detail: "Parsing clinical context and routing request…" },
  { icon: "🔍", label: "Vector Search", detail: "Semantic search across facility registry…" },
  { icon: "🛡️", label: "Trust Validator", detail: "Verifying evidence integrity per facility…" },
  { icon: "🗺️", label: "Geospatial Engine", detail: "Mapping coordinates and distances…" },
  { icon: "📊", label: "SQL Agent", detail: "Querying Databricks warehouse for records…" },
  { icon: "🤖", label: "LLM Judge", detail: "LLM-as-a-Judge validating result quality…" },
  { icon: "📝", label: "Synthesis Agent", detail: "Assembling final answer with citations…" },
];

function AgentProgressPanel({ busy, stepIndex }: { busy: boolean; stepIndex: number }) {
  if (!busy) return null;
  return (
    <div style={{ padding: "16px", background: "#061328", border: "1px solid #172c4d", borderRadius: "8px", marginBottom: "10px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
        <LoaderCircle className="spin" style={{ width: "14px", color: "#8d46ff" }} />
        <b style={{ fontSize: "10px", color: "#b8c4d9" }}>Agent pipeline running…</b>
        <span style={{ marginLeft: "auto", fontSize: "8px", color: "#5f6d84" }}>This may take 30–90 seconds</span>
      </div>
      {AGENT_STEPS.map((step, i) => {
        const done = i < stepIndex;
        const active = i === stepIndex;
        const pending = i > stepIndex;
        return (
          <div key={step.label} style={{
            display: "flex", alignItems: "center", gap: "10px", padding: "8px 10px", marginBottom: "4px",
            borderRadius: "6px", background: active ? "#0c1d37" : "transparent",
            border: active ? "1px solid #1e3a5f" : "1px solid transparent",
            opacity: pending ? 0.35 : 1, transition: "all 0.3s"
          }}>
            <span style={{ fontSize: "14px", width: "20px", textAlign: "center" }}>
              {done ? "✅" : active ? step.icon : "⏳"}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: "9px", fontWeight: 600, color: done ? "#39d99b" : active ? "#b8c4d9" : "#5f6d84" }}>
                {step.label}
              </div>
              {active && <div style={{ fontSize: "8px", color: "#6b7c93", marginTop: "2px" }}>{step.detail}</div>}
            </div>
            {active && <LoaderCircle className="spin" style={{ width: "11px", color: "#8d46ff", flexShrink: 0 }} />}
            {done && <span style={{ fontSize: "8px", color: "#39d99b", flexShrink: 0 }}>Done</span>}
          </div>
        );
      })}
    </div>
  );
}

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const [query, setQuery] = useState("Fever and difficulty breathing for 2 days; need emergency care");
  const [state, setState] = useState("Bihar");
  const [topK, setTopK] = useState(10);
  const [triage, setTriage] = useState<TriageResponse | null>(null);
  const [match, setMatch] = useState<MatchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [agentStep, setAgentStep] = useState(0);
  const [error, setError] = useState("");
  const [systemOk, setSystemOk] = useState<boolean | null>(null);
  const [systemDetail, setSystemDetail] = useState("");
  const [selected, setSelected] = useState<Facility | null>(null);
  const [verdictFilter, setVerdictFilter] = useState("ALL");
  const [sort, setSort] = useState("score");
  const [detailTab, setDetailTab] = useState<"overview" | "evidence" | "contacts">("overview");
  const [contact, setContact] = useState<Record<string, any> | null>(null);
  const [contactBusy, setContactBusy] = useState(false);
  const [referral, setReferral] = useState<Record<string, any> | null>(null);
  const stepTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    health()
      .then(x => {
        setSystemOk(Boolean(x.ok));
        const integrations = x.integrations as Record<string, any> | undefined;
        if (integrations) {
          const parts: string[] = [];
          if (integrations.tavily?.configured) parts.push("Tavily ✓");
          if (integrations.twilio?.configured) parts.push("Twilio ✓");
          setSystemDetail(parts.join(" · ") || "Databricks connected");
        }
      })
      .catch(() => {
        setSystemOk(false);
        setSystemDetail("Cannot reach /healthz — check backend deployment");
      });
  }, []);

  const facilities = useMemo(() =>
    match ? deriveFacilities(match, triage?.capabilities_needed || []) : [],
    [match, triage]
  );

  const shown = useMemo(() =>
    facilities
      .filter(f => verdictFilter === "ALL" || f.verdict === verdictFilter)
      .sort((a, b) => sort === "name" ? a.name.localeCompare(b.name) : b.score - a.score),
    [facilities, verdictFilter, sort]
  );

  const counts = {
    verified: facilities.filter(f => f.verdict === "VERIFIED").length,
    review: facilities.filter(f => f.verdict === "REVIEW").length,
    suspicious: facilities.filter(f => f.verdict === "SUSPICIOUS").length,
  };

  function startStepTimer() {
    setAgentStep(0);
    let step = 0;
    // Advance steps on a realistic schedule matching the actual pipeline
    const delays = [2000, 5000, 8000, 12000, 18000, 30000, 50000];
    const advance = (idx: number) => {
      if (idx >= AGENT_STEPS.length) return;
      stepTimerRef.current = setTimeout(() => {
        step = idx;
        setAgentStep(idx);
        advance(idx + 1);
      }, delays[idx] || 8000);
    };
    advance(0);
  }

  function stopStepTimer() {
    if (stepTimerRef.current) {
      clearTimeout(stepTimerRef.current);
      stepTimerRef.current = null;
    }
    setAgentStep(AGENT_STEPS.length); // mark all done
  }

  async function run() {
    setBusy(true);
    setError("");
    setSelected(null);
    setMatch(null);
    startStepTimer();
    try {
      const t = await analyze(query.trim());
      setTriage(t);
      const m = await matchFacilities(t.session_id, state, topK);
      // Debug logging in dev
      if (process.env.NODE_ENV === "development") {
        const rows = (m.search_result || []).map((item: any, index: number) => ({
          index: index + 1,
          facility: item.name || "Unknown",
          state: item.state_normalized || "",
          pin: item.pin_code || "",
          latitude: item.latitude ?? item.lat ?? null,
          longitude: item.longitude ?? item.lon ?? null,
          mappable: Boolean((item.latitude ?? item.lat) && (item.longitude ?? item.lon)),
        }));
        console.groupCollapsed("[CareCompass] Facility matching API response and coordinates");
        console.log("Raw response:", m);
        console.table(rows);
        if (!rows.some((row: any) => row.mappable)) {
          console.warn("No coordinates in search_result — map will be empty.");
        }
        console.groupEnd();
      }
      localStorage.setItem("carecompass-last-match", JSON.stringify(m));
      setMatch(m);
      const fs = deriveFacilities(m, t.capabilities_needed || []);
      setSelected(fs[0] || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed — check backend");
    } finally {
      stopStepTimer();
      setBusy(false);
    }
  }

  async function choose(f: Facility) {
    setSelected(f);
    setDetailTab("overview");
    setContact(null);
    setReferral(null);
  }

  async function loadContact() {
    if (!selected) return;
    setDetailTab("contacts");
    if (contact) return;
    setContactBusy(true);
    try {
      setContact(await enrich(selected.name, selected.state));
    } catch (e) {
      setContact({ error: e instanceof Error ? e.message : "Enrichment unavailable" });
    } finally {
      setContactBusy(false);
    }
  }

  async function refer() {
    if (!selected || !triage) return;
    try {
      setReferral(await referralPreview(triage.session_id, selected.name, query, contact?.enrichment?.phone_estimated || ""));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Referral preview failed");
    }
  }

  async function referFacility(target: Facility) {
    if (!triage) return;
    try {
      setReferral(await referralPreview(triage.session_id, target.name, query, ""));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Referral preview failed");
    }
  }

  if (!mounted) return null;

  // Raw result count before deriveFacilities filtering
  const rawSearchHits = Array.isArray(match?.search_result) ? match.search_result.length : 0;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Compass /></span>
          <div><strong>CareCompass</strong><small>India</small></div>
        </div>
        <div className={`health-card ${systemOk === false ? "down" : ""}`}>
          <span>System health</span>
          <b><i />{systemOk === null ? "Checking services…" : systemOk ? "API operational" : "API unavailable"}</b>
          {systemOk === false && (
            <div style={{ fontSize: "7px", color: "#f46b82", marginTop: "4px", lineHeight: 1.4 }}>
              {systemDetail || "Backend unreachable. Check Databricks Apps deployment."}
            </div>
          )}
          {systemOk === true && systemDetail && (
            <div style={{ fontSize: "7px", color: "#39d99b", marginTop: "4px" }}>{systemDetail}</div>
          )}
        </div>
        <button className="new-triage" onClick={() => { setMatch(null); setTriage(null); setSelected(null); }}>
          <ClipboardPlus />New triage
        </button>
        <nav className="side-nav">
          <Link className="active" href="/"><LayoutDashboard />Dashboard</Link>
          <Link href="/mission-planner"><ClipboardPlus />Mission Planner</Link>
        </nav>
        <div className="agent-card">
          <div><span>AI model status</span><i className={systemOk ? "online" : ""} /></div>
          <b>{systemOk ? "Backend connected" : "Check configuration"}</b>
          {["Data Extractor", "Trust Validator", "Medical Standards Agent", "Geospatial Engine", "Policy Checker"].map(x => (
            <small key={x}><Check />{x}</small>
          ))}
        </div>
        <p className="version">CareCompass · evidence-backed</p>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="mini-brand"><Compass /><b>CareCompass — India</b></div>
          <nav>
            <Link className="active" href="/">Triage &amp; Matching</Link>
            <Link href="/mission-planner">Mission Planner</Link>
            <Link href="/desert-map">Desert Map</Link>
          </nav>
          <div className="top-actions">
            <ThemeToggle />
            <button className="notice"><Bell /><i>3</i></button>
            <span className="avatar">UI</span>
            <div className="profile"><b>Umair Imran</b><small>Clinician / NGO</small></div>
            <ChevronDown />
          </div>
        </header>

        <section className="hero-strip">
          <div className="india-orbit" />
          <div className="impact">
            <span>🇮🇳</span>
            <p>Powering <b>1.4 Billion Lives</b><small>Verified · Transparent · Impactful</small></p>
          </div>
        </section>

        <div className="content-grid">
          <section className="main-column">
            {/* Input form */}
            <section className="triage-form">
              <div className="triage-form-head">
                <div><span>New capability triage</span><h1>Find evidence-backed facilities</h1></div>
                {triage?.red_flags?.[0] && <span className="urgent-pill"><HeartPulse />{label(triage.red_flags[0])}</span>}
              </div>
              <div className="triage-input-grid">
                <label className="care-input">
                  <span>Symptoms, urgency, and clinical context</span>
                  <textarea value={query} onChange={e => setQuery(e.target.value)}
                    placeholder="e.g. Fever and difficulty breathing for 2 days; need emergency care" rows={3} />
                </label>
                <div className="triage-options">
                  <label>
                    <span>Region / State</span>
                    <select value={state} onChange={e => setState(e.target.value)}>
                      {STATES.map(item => <option key={item} value={item}>{item}</option>)}
                    </select>
                  </label>
                  <label className="results-slider">
                    <span>Results <b>{topK}</b></span>
                    <input type="range" min="1" max="20" step="1" value={topK} onChange={e => setTopK(Number(e.target.value))} />
                    <small><i>1</i><i>20</i></small>
                  </label>
                </div>
              </div>
              <button className="triage-submit" disabled={busy || !query.trim()} onClick={run}>
                {busy ? <LoaderCircle className="spin" /> : <Sparkles />}
                {busy ? "Agent pipeline running…" : match ? "Analyze again & refresh matches" : "Analyze & find matching facilities"}
              </button>
            </section>

            {/* Compact search bar */}
            <div className="query-card">
              <Search />
              <div className="query-fields">
                <input value={query} onChange={e => setQuery(e.target.value)} aria-label="Care need" />
                <div>
                  <span><MapPin />{state}</span>
                  {triage?.red_flags?.[0] && <span className="urgent"><HeartPulse />{label(triage.red_flags[0])}</span>}
                  <span><Database />{facilities.length || topK} results</span>
                </div>
              </div>
              <button className="edit"><Pencil />Edit</button>
              <button className="analyze" disabled={busy || !query.trim()} onClick={run}>
                {busy ? <LoaderCircle className="spin" /> : <Sparkles />}
                {busy ? "Agents working…" : match ? "Analyze again" : "Analyze & match"}
              </button>
            </div>

            {error && (
              <div className="error">
                <AlertTriangle />{error}
                <button onClick={() => setError("")}><X /></button>
              </div>
            )}

            {/* Metrics */}
            <div className="metric-row">
              <Metric value={counts.verified} title="Verified match" note="High confidence facilities" tone="green" icon={<ShieldCheck />} />
              <Metric value={counts.review} title="Needs review" note="Requires human verification" tone="amber" icon={<CircleGauge />} />
              <Metric value={counts.suspicious} title="Insufficient evidence" note="Low confidence" tone="red" icon={<AlertTriangle />} />
              <Metric value={facilities.length} title="Total analyzed" note="Across returned sources" tone="blue" icon={<Database />} />
            </div>

            {/* Filters */}
            <div className="controls">
              <select value={verdictFilter} onChange={e => setVerdictFilter(e.target.value)}>
                <option value="ALL">All evidence statuses</option>
                <option value="VERIFIED">Verified</option>
                <option value="REVIEW">Needs review</option>
                <option value="SUSPICIOUS">Insufficient evidence</option>
              </select>
              <button><Filter />Filters</button>
              <select value={sort} onChange={e => setSort(e.target.value)}>
                <option value="score">Sort: best match</option>
                <option value="name">Sort: facility name</option>
              </select>
              <div className="view-toggle"><span>View</span><List /></div>
            </div>

            {/* Desert warning */}
            {match?.desert_analysis && (
              <div className="error" style={{ background: "#1e0d12", borderColor: "#702a46", color: "#ff92aa", marginBottom: "10px" }}>
                <AlertTriangle /><b>Data Desert Warning:</b>&nbsp;{match.desert_analysis}
              </div>
            )}

            {/* Agent progress panel (shown during busy) */}
            <AgentProgressPanel busy={busy} stepIndex={agentStep} />

            {/* Results */}
            <div className="results-map-grid">
              <div className="facility-list">
                {!match && !busy && (
                  <div className="empty-state">
                    <span><Hospital /></span>
                    <h2>Start with a care need</h2>
                    <p>The AI agents will translate symptoms to capabilities, retrieve matching facilities from the Databricks registry, and validate the evidence.</p>
                    <button onClick={run}><Sparkles />Analyze sample query</button>
                  </div>
                )}
                {busy && !shown.length && (
                  <div className="empty-state">
                    <LoaderCircle className="spin" />
                    <h2>Agent pipeline running</h2>
                    <p>LangGraph is orchestrating the supervisor → search → trust → synthesis pipeline against Databricks Vector Search and the SQL Warehouse.</p>
                  </div>
                )}
                {match && !busy && !shown.length && (
                  <div className="empty-state">
                    <AlertTriangle />
                    <h2>No facility rows returned</h2>
                    <p style={{ lineHeight: 1.6 }}>
                      The Vector Search index returned <b>{rawSearchHits}</b> raw hits for "{state}".
                      {rawSearchHits === 0
                        ? " This usually means the index is not yet populated, the VECTOR_SEARCH_INDEX env var is wrong, or the endpoint is cold."
                        : " The rows exist but failed derivation — check that the index contains the required columns (name, latitude, longitude, trust_score)."}
                    </p>
                    {rawSearchHits > 0 && match?.search_result && (
                      <div style={{ marginTop: "12px", fontSize: "8px", textAlign: "left", background: "#0a1931", border: "1px solid #1a2b4b", borderRadius: "6px", padding: "10px", maxHeight: "120px", overflow: "auto" }}>
                        <b style={{ color: "#8d46ff" }}>Raw search_result preview ({rawSearchHits} records):</b>
                        {(match.search_result as any[]).slice(0, 3).map((row: any, i: number) => (
                          <div key={i} style={{ marginTop: "6px", color: "#8ca0b8" }}>
                            <b style={{ color: "#b8c4d9" }}>#{i + 1}: {row.name || "Unknown"}</b>
                            {" · "}{row.state_normalized || row.state || "?"}{" · "}
                            lat={String(row.latitude ?? row.lat ?? "—")}, lon={String(row.longitude ?? row.lon ?? "—")}
                          </div>
                        ))}
                      </div>
                    )}
                    {/* Link to readiness endpoint */}
                    <p style={{ fontSize: "8px", marginTop: "10px" }}>
                      <a href="/readiness" target="_blank" rel="noreferrer" style={{ color: "#4388ff" }}>
                        View /readiness endpoint →
                      </a>
                    </p>
                  </div>
                )}
                {shown.map((f, i) => (
                  <FacilityCard
                    key={f.id} facility={f} rank={i + 1}
                    selected={selected?.id === f.id}
                    onSelect={() => choose(f)}
                    onRefer={() => { choose(f); void referFacility(f); }}
                    onEvidence={() => setDetailTab("evidence")}
                  />
                ))}
                {shown.length > 0 && (
                  <div className="list-footer">
                    Showing {shown.length} evidence-backed facilities
                    {match?.llm_judge && (
                      <span style={{ display: "inline-block", marginTop: "10px", padding: "6px 12px", background: "#0a1b36", border: "1px solid #152b4b", borderRadius: "5px", color: "#39d99b" }} title={match.llm_judge.judge_note}>
                        <ShieldCheck style={{ width: "12px", verticalAlign: "middle", marginRight: "5px" }} />
                        LLM Judge Trust Score: {match.llm_judge.trust_score}%
                      </span>
                    )}
                  </div>
                )}
              </div>
              <MapPanel facilities={shown} selectedId={selected?.id} onSelect={choose} />
            </div>
          </section>

          {/* Detail panel */}
          <aside className="detail-panel">
            {selected ? (
              <>
                <div className="detail-head">
                  <div>
                    <h2>{selected.name}</h2>
                    <span className={`status ${selected.verdict.toLowerCase()}`}>
                      <ShieldCheck />
                      {selected.verdict === "VERIFIED" ? "Verified match" : selected.verdict === "REVIEW" ? "Needs review" : "Insufficient evidence"}
                    </span>
                  </div>
                  <button onClick={() => setSelected(null)}><X /></button>
                </div>
                <div className="tabs">
                  <button className={detailTab === "overview" ? "active" : ""} onClick={() => setDetailTab("overview")}>Overview</button>
                  <button className={detailTab === "evidence" ? "active" : ""} onClick={() => setDetailTab("evidence")}>Evidence</button>
                  <button className={detailTab === "contacts" ? "active" : ""} onClick={loadContact}>Contacts</button>
                </div>
                {detailTab === "overview" && <Overview facility={selected} />}
                {detailTab === "evidence" && <Evidence facility={selected} match={match} />}
                {detailTab === "contacts" && <Contacts data={contact} loading={contactBusy} />}
                <div className="detail-actions">
                  <button className="refer" onClick={refer}><Send />Refer this facility</button>
                  {referral && (
                    <div className="referral-preview">
                      <b>Referral preview ready</b>
                      <p>{String(referral.body || "")}</p>
                      <small>Preview only. Confirm the recipient before sending externally.</small>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="detail-empty">
                <ShieldCheck />
                <h2>Facility evidence</h2>
                <p>Select a recommendation to inspect its trust score, capabilities, citations, and contact enrichment.</p>
              </div>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
}

function Metric({ value, title, note, tone, icon }: { value: number; title: string; note: string; tone: string; icon: React.ReactNode }) {
  return (
    <div className={`metric ${tone}`}>
      <div><strong>{value}</strong><b>{title}</b><small>{note}</small></div>
      {icon}
    </div>
  );
}

function FacilityCard({ facility: f, rank, selected, onSelect, onRefer, onEvidence }: {
  facility: Facility; rank: number; selected: boolean;
  onSelect: () => void; onRefer: () => void; onEvidence: () => void;
}) {
  const photo = ILLUSTRATIVE_HOSPITAL_IMAGES[(rank - 1) % ILLUSTRATIVE_HOSPITAL_IMAGES.length];
  const [correctionSent, setCorrectionSent] = useState(false);
  const handleCorrection = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const reason = window.prompt("What is incorrect about this facility data?");
    if (reason) {
      await submitCorrection(f.name, reason).catch(() => {});
      setCorrectionSent(true);
    }
  };
  return (
    <article className={`facility-card ${f.verdict.toLowerCase()} ${selected ? "selected" : ""}`} onClick={onSelect}>
      <div className="rank">{rank}</div>
      <div className="hospital-thumb hospital-photo" style={{
        backgroundImage: `linear-gradient(180deg,transparent 45%,rgba(2,13,34,.92)),url(${photo})`,
        backgroundPosition: `${35 + (rank % 3) * 15}% center`
      }}>
        <span>Illustrative image</span>
      </div>
      <div className="facility-copy">
        <h3>{f.name}<ShieldCheck /></h3>
        <p><MapPin />{[f.city, f.state, f.pin].filter(Boolean).join(" · ")}</p>
        <div className="capabilities">
          {f.capabilities.slice(0, 3).map(x => <span key={x}>{label(x)}</span>)}
          {f.flags[0] && <span className="warning">{f.flags[0].slice(0, 45)}</span>}
        </div>
        <small>
          <Database />{f.citations.length} evidence receipts ·{" "}
          <a style={{ color: "#3897ff", textDecoration: "underline" }} onClick={handleCorrection}>
            {correctionSent ? "Reported ✓" : "Report Incorrect Data"}
          </a>
        </small>
      </div>
      <div className="facility-score">
        <strong>{Math.round(f.score * 100)}%</strong>
        <span>{f.verdict === "VERIFIED" ? "Verified match" : f.verdict === "REVIEW" ? "Needs review" : "Insufficient evidence"}</span>
        <i><b style={{ width: `${Math.round(f.score * 100)}%` }} /></i>
        <div>
          <button onClick={e => { e.stopPropagation(); onSelect(); onEvidence(); }}>View evidence</button>
          <button className="refer-mini" onClick={e => { e.stopPropagation(); onRefer(); }}><Send />Refer</button>
        </div>
      </div>
      <Bookmark className="bookmark" />
    </article>
  );
}

function Overview({ facility: f }: { facility: Facility }) {
  return (
    <>
      <section className="trust-box">
        <span>Trust score</span>
        <div>
          <strong>{Math.round(f.score * 100)}%</strong>
          <b>{f.verdict === "VERIFIED" ? "Verified match" : f.verdict === "REVIEW" ? "Needs human review" : "Insufficient evidence"}</b>
        </div>
        <i><b style={{ width: `${Math.round(f.score * 100)}%` }} /></i>
        <small>Evidence consistency score—not accreditation or live availability.</small>
      </section>
      <section className="panel-box">
        <h3>Key capabilities</h3>
        {f.capabilities.length
          ? f.capabilities.map((x, i) => (
            <div className="cap-row" key={`${x}-${i}`}><Check /><p><b>{label(x)}</b><small>Listed in returned facility evidence</small></p></div>
          ))
          : <p className="muted">No structured capabilities returned.</p>
        }
        {f.flags.map((x, i) => <div className="flag-row" key={`${x}-${i}`}><AlertTriangle /><p>{x}</p></div>)}
      </section>
      <section className="panel-box">
        <h3>Facility context</h3>
        <p className="description">{f.description}</p>
        <p className="location-line"><MapPin />{[f.city, f.state, f.pin].filter(Boolean).join(" · ")}</p>
      </section>
    </>
  );
}

function Evidence({ facility: f, match }: { facility: Facility; match: MatchResponse | null }) {
  return (
    <section className="panel-box evidence-box">
      <h3>
        <ShieldCheck style={{ width: "14px", verticalAlign: "bottom", marginRight: "5px", color: "#12d68d" }} />
        MLFlow Traceability
      </h3>
      <p style={{ fontSize: "8px", color: "#8696ad", marginBottom: "12px" }}>
        Showing exact retrieval and synthesis extraction trace for transparency.
      </p>
      {match?.llm_judge && (
        <div style={{ padding: "8px", borderLeft: "3px solid #12d68d", background: "#0a1b36", marginBottom: "12px" }}>
          <b style={{ color: "#12d68d", fontSize: "9px", display: "block" }}>Trust Validation Completed</b>
          <span style={{ fontSize: "8px", color: "#a4afc3" }}>{match.llm_judge.judge_note}</span>
        </div>
      )}
      <h3>Evidence receipts</h3>
      {f.citations.length
        ? f.citations.map((c, i) => (
          <div className="evidence-row" key={i}>
            <span>{i + 1}</span>
            <p>
              <b>{label(String(c.source || "Dataset evidence"))}</b>
              <small>{String(c.evidence_snippet || c.description || c.field || "Supporting record returned by the agent")}</small>
              <em>Confidence {Math.round(Number(c.confidence || 0) * 100)}%</em>
            </p>
          </div>
        ))
        : <p className="muted">No normalized citations were returned for this facility.</p>
      }
    </section>
  );
}

function Contacts({ data, loading }: { data: Record<string, any> | null; loading: boolean }) {
  if (loading) return <div className="loading-contact"><LoaderCircle className="spin" />Searching public contact sources…</div>;
  if (!data) return null;
  if (data.error || data.success === false) return <div className="contact-warning"><AlertTriangle />{String(data.error || "Contact enrichment unavailable")}</div>;
  const e = data.enrichment || {};
  return (
    <section className="panel-box">
      <h3>Estimated public contacts</h3>
      <div className="contact-row"><Phone /><p><b>{e.phone_estimated || "No phone found"}</b><small>Verify before use</small></p></div>
      <div className="contact-row"><Compass /><p><b>{e.website_estimated || "No website found"}</b><small>{e.hours_note || "Hours not verified"}</small></p></div>
      <p className="contact-disclaimer">Tavily enrichment is heuristic public-web information, not independently verified.</p>
    </section>
  );
}
