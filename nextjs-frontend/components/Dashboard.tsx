"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, MapPin, Database, HeartPulse, Send, ShieldCheck } from "lucide-react";
import { analyze, matchFacilities, health, type MatchResponse, type TriageResponse } from "@/lib/api";
import { deriveFacilities, type Facility } from "@/lib/facilities";
import ThemeToggle from "./ThemeToggle";

const MapPanel = dynamic(() => import("./MapPanel"), { ssr: false });

const label = (s: string) => s.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]/g, " ").replace(/\b\w/g, c => c.toUpperCase());

const AGENT_STEPS = [
  { icon: "🧠", label: "Supervisor Agent", detail: "Parsing clinical context and routing request…" },
  { icon: "🔍", label: "Vector Search", detail: "Semantic search across facility registry…" },
  { icon: "🛡️", label: "Trust Validator", detail: "Verifying evidence integrity per facility…" },
  { icon: "🗺️", label: "Geospatial Engine", detail: "Mapping coordinates and distances…" },
  { icon: "🤖", label: "LLM Judge", detail: "LLM-as-a-Judge validating result quality…" },
  { icon: "📝", label: "Synthesis Agent", detail: "Assembling final answer with citations…" },
];

function AgentProgress({ busy, stepIndex }: { busy: boolean; stepIndex: number }) {
  if (!busy) return null;
  return (
    <div className="agent-progress">
      <div className="agent-progress-header">
        <span className="spin">⏳</span>
        <b>Agent pipeline running…</b>
      </div>
      {AGENT_STEPS.map((step, i) => {
        const done = i < stepIndex;
        const active = i === stepIndex;
        const pending = i > stepIndex;
        return (
          <div key={step.label} className={`agent-step ${active ? "active" : ""} ${pending ? "pending" : ""}`}>
            <span>{done ? "✅" : active ? step.icon : "⏳"}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, color: done ? "var(--green)" : active ? "white" : "var(--slate)" }}>
                {step.label}
              </div>
              {active && <div style={{ fontSize: "11px", color: "var(--light)", marginTop: "2px" }}>{step.detail}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const [query, setQuery] = useState("");
  const [triage, setTriage] = useState<TriageResponse | null>(null);
  const [match, setMatch] = useState<MatchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [agentStep, setAgentStep] = useState(0);
  const [error, setError] = useState("");
  const [systemOk, setSystemOk] = useState<boolean | null>(null);
  const [selected, setSelected] = useState<Facility | null>(null);
  const stepTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    health()
      .then(x => setSystemOk(Boolean(x.ok)))
      .catch(() => setSystemOk(false));
  }, []);

  const facilities = useMemo(() =>
    match ? deriveFacilities(match, triage?.capabilities_needed || []) : [],
    [match, triage]
  );

  function startStepTimer() {
    setAgentStep(0);
    let step = 0;
    const delays = [1500, 4000, 7000, 10000, 13000, 16000];
    const advance = (idx: number) => {
      if (idx >= AGENT_STEPS.length) return;
      stepTimerRef.current = setTimeout(() => {
        step = idx;
        setAgentStep(idx);
        advance(idx + 1);
      }, delays[idx] || 5000);
    };
    advance(0);
  }

  function stopStepTimer() {
    if (stepTimerRef.current) clearTimeout(stepTimerRef.current);
    setAgentStep(AGENT_STEPS.length);
  }

  async function run(overrideQuery?: string) {
    const textToRun = overrideQuery || query;
    if (!textToRun.trim()) return;
    setQuery(textToRun); // update input box if chip was clicked
    setBusy(true);
    setError("");
    setSelected(null);
    setMatch(null);
    startStepTimer();
    try {
      const t = await analyze(textToRun.trim());
      setTriage(t);
      // Auto-detect state if possible, otherwise empty string and backend handles
      const m = await matchFacilities(t.session_id, "", 10);
      setMatch(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed — check backend");
    } finally {
      stopStepTimer();
      setBusy(false);
    }
  }

  if (!mounted) return null;

  return (
    <div className="vc-app">
      <nav className="vc-nav">
        <div className="vc-logo">
          <div className="vc-logo-icon">
            <HeartPulse />
          </div>
          <div className="vc-logo-text">
            <h1>CARECOMPASS</h1>
            <p>Healthcare Intelligence Platform</p>
          </div>
        </div>
        <div className="vc-tabs">
          <Link href="/" className="vc-tab active">
            <span className="vc-tab-icon">💓</span>
            Referral Copilot
          </Link>
          <Link href="/desert-map" className="vc-tab">
            <span className="vc-tab-icon">📊</span>
            Analytics
          </Link>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "10px" }}>
          {systemOk === null ? "Checking..." : systemOk ? (
            <span style={{ fontSize: "12px", color: "var(--green)" }}>● Backend Connected</span>
          ) : (
            <span style={{ fontSize: "12px", color: "var(--amber)" }}>● Partial / Checking Services</span>
          )}
          <ThemeToggle />
        </div>
      </nav>

      <div className="vc-emergency">
        🚨 LIFE-THREATENING EMERGENCY — CALL 108 IMMEDIATELY
      </div>

      <div className="vc-view vc-view-pulse">
        <div className="vc-chat">
          <div className="vc-chat-header">
            <div className="vc-tag">💓 Pulse · AI Agent</div>
            <h2>Referral Copilot</h2>
            <p>Ask about any facility in India — by city, state, specialty, or capability</p>
          </div>

          <div className="vc-stats">
            <div className="vc-stat">
              <div className="vc-stat-val">~10K</div>
              <div className="vc-stat-lbl">Facilities</div>
            </div>
            <div className="vc-stat">
              <div className="vc-stat-val">29+</div>
              <div className="vc-stat-lbl">States</div>
            </div>
            <div className="vc-stat">
              <div className="vc-stat-val">Llama 3.3</div>
              <div className="vc-stat-lbl">AI Model</div>
            </div>
          </div>

          <div className="vc-messages">
            <div className="vc-msg vc-msg--agent">
              <div className="vc-bubble">
                Hello! I'm your AI Referral Copilot. Tell me the patient's symptoms or requirements, and I'll find evidence-backed facilities.
              </div>
            </div>

            {query && (busy || match || error) && (
              <div className="vc-msg vc-msg--user">
                <div className="vc-bubble">{query}</div>
              </div>
            )}

            {(busy || match || error) && (
              <div className="vc-msg vc-msg--agent">
                <div className="vc-bubble">
                  <AgentProgress busy={busy} stepIndex={agentStep} />
                  
                  {error && (
                    <div className="vc-error">
                      <AlertTriangle size={16} />
                      {error}
                    </div>
                  )}

                  {!busy && match && match.desert_analysis && (
                    <div className="vc-validation" style={{ borderColor: "var(--amber)", backgroundColor: "rgba(245, 158, 11, 0.1)" }}>
                      <AlertTriangle className="vc-val-icon" style={{ color: "var(--amber)" }} />
                      <div className="vc-val-text">
                        <b>Data Desert Warning</b>
                        <span className="vc-val-note" style={{ color: "var(--text)" }}>{match.desert_analysis}</span>
                      </div>
                    </div>
                  )}

                  {!busy && triage && triage.capabilities_needed && triage.capabilities_needed.length > 0 && (
                    <div className="vc-validation">
                      <HeartPulse className="vc-val-icon" />
                      <div className="vc-val-text">
                        Extracted Capabilities: <b>{triage.capabilities_needed.map(label).join(", ")}</b>
                      </div>
                    </div>
                  )}

                  {!busy && match && facilities.length === 0 && !error && (
                    <div className="vc-error" style={{ marginTop: "10px" }}>
                      No exact facilities found for this query in the Databricks index.
                    </div>
                  )}

                  {!busy && match && facilities.map((f, i) => (
                    <FacilityCard key={f.id} facility={f} selected={selected?.id === f.id} onSelect={() => setSelected(f)} />
                  ))}

                  {!busy && match && match.llm_judge && (
                    <div className="vc-validation" style={{ borderColor: "var(--green)", marginTop: "14px" }}>
                      <ShieldCheck className="vc-val-icon" style={{ color: "var(--green)" }} />
                      <div className="vc-val-text">
                        <b>Validated by Llama 3.3 — Trust Score: {match.llm_judge.trust_score}%</b>
                        <span className="vc-val-note">{match.llm_judge.judge_note}</span>
                      </div>
                    </div>
                  )}

                </div>
              </div>
            )}
          </div>

          <div id="vc-suggestions" style={{ padding: "8px 12px", display: "flex", flexWrap: "wrap", gap: "6px", borderTop: "1px solid var(--border)" }}>
            {["Compare hospitals in Delhi vs Dehradun", "Cardiac centers in Delhi", "Emergency hospitals in Mumbai"].map(chip => (
              <span key={chip} className="vc-chip" style={{ background: "rgba(14,165,233,.1)", border: "1px solid rgba(14,165,233,.25)", color: "var(--teal)", borderRadius: "99px", padding: "5px 11px", fontSize: "12px", cursor: "pointer", whiteSpace: "nowrap" }} onClick={() => run(chip)}>
                {chip}
              </span>
            ))}
          </div>

          <div className="vc-input-row">
            <textarea
              className="vc-input"
              placeholder="Ask about healthcare facilities…"
              rows={1}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  run();
                }
              }}
            />
            <button className="vc-send" disabled={busy || !query.trim()} onClick={() => run()}>
              <Send />
            </button>
          </div>
        </div>

        <div className="vc-map-panel">
          <MapPanel facilities={facilities} selectedId={selected?.id} onSelect={setSelected} />
        </div>
      </div>
    </div>
  );
}

function FacilityCard({ facility: f, selected, onSelect }: { facility: Facility; selected: boolean; onSelect: () => void }) {
  return (
    <div className={`vc-facility-card ${f.verdict.toLowerCase()} ${selected ? "selected" : ""}`} onClick={onSelect} style={{ cursor: "pointer", opacity: selected ? 1 : 0.9 }}>
      <h3>{f.name}</h3>
      <p><MapPin size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: "4px" }}/>{[f.city, f.state, f.pin].filter(Boolean).join(" · ")}</p>
      <div className="caps">
        {f.capabilities.slice(0, 3).map(x => <span key={x}>{label(x)}</span>)}
      </div>
      <div style={{ marginTop: "10px", fontSize: "11px", display: "flex", justifyContent: "space-between", color: "var(--slate)" }}>
        <span><Database size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: "4px" }} />{f.citations.length} evidence sources</span>
        <strong style={{ color: f.verdict === "VERIFIED" ? "var(--green)" : f.verdict === "REVIEW" ? "var(--amber)" : "var(--coral)" }}>
          {f.verdict} ({Math.round(f.score * 100)}%)
        </strong>
      </div>
    </div>
  );
}
