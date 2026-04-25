"""Trust Scorer — deterministic rules + two-pass LLM (extractor + validator) + disagreement."""

from __future__ import annotations

import json

import mlflow

from src.citations import normalize_citation
from src.state import AgentState
from src.tools.model_serving_tool import query_llm
from src.tools.vector_search_tool import query_vector_search
from src.utils.trust_rules import facility_dict_to_trust

EXTRACTOR_PROMPT = """You are Pass 1 — a fact extractor for Indian healthcare facilities (CareCompass).

For EACH facility in the input JSON array, return ONE JSON object (array of same length) with:
{
  "name": "from data",
  "extracted_claims": ["short bullet claim strings grounded ONLY in the record"],
  "uncertainty_0_1": 0.0-1.0,
  "key_evidence_phrase": "shortest quote from description/specialty/equipment text"
}

JSON arrays [] in the source mean "no listed evidence" — do not invent equipment or procedures.
Return ONLY a JSON array, no markdown."""

VALIDATOR_PROMPT = """You are Pass 2 — a validator against basic medical-operations sanity (not diagnosis).

For EACH object from Pass 1 (matched by `name` when possible) plus the original facility snapshot,
return ONE JSON object (array) with:
{
  "name": "string",
  "contradiction_flags": ["..."],
  "validator_score_0_1": 0.0-1.0,
  "verdict_suggestion": "VERIFIED" | "REVIEW" | "SUSPICIOUS"
}

Rules (examples):
- Major surgery/appendectomy/cesarean claims need OT/surgery + anesthesia/OT evidence in text or capability fields.
- ICU/critical/ventilator claims need equipment or explicit ICU capability, else flag.
- 24/7 emergency needs explicit text; else uncertain.

Return ONLY a JSON array, no markdown."""


def _parse_json_array(raw: str) -> list[dict] | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()
    s = s.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        out = json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if isinstance(out, list):
        return [x for x in out if isinstance(x, dict)]
    if isinstance(out, dict):
        return [out]
    return None


def _merge_row(
    det: dict,
    ext: dict | None,
    val: dict | None,
) -> dict:
    n = str(
        (ext or {}).get("name")
        or (val or {}).get("name")
        or det.get("facility")
        or "?"
    )
    d_adj = float(det.get("adjusted_0_1", 0.5) or 0.5)
    ext_u = float((ext or {}).get("uncertainty_0_1", 0.3) or 0.0)
    val_s = float((val or {}).get("validator_score_0_1", 0.6) or 0.6)
    det_flags = list(det.get("flags") or [])
    con_flags = list((val or {}).get("contradiction_flags") or [])

    # Disagreement: extractor uncertain vs validator strict, or det vs val
    disagreements: list[str] = []
    if ext_u > 0.5 and val_s < 0.5:
        disagreements.append("High extractor uncertainty but validator is strict (possible conflict).")
    if abs(d_adj - val_s) > 0.25:
        disagreements.append("Deterministic trust differs from validator score by >0.25.")
    if (val or {}).get("verdict_suggestion") == "VERIFIED" and det_flags:
        disagreements.append("Validator VERIFIED but deterministic rules raised flags (review).")

    # Combined score: damped by uncertainty and flags
    combined = 0.45 * d_adj + 0.35 * val_s + 0.2 * max(0.0, 1.0 - ext_u)
    if disagreements:
        combined *= 0.85
    if con_flags or det_flags:
        combined *= 0.9
    if combined < 0.35:
        fin_v = "SUSPICIOUS"
    elif combined < 0.55:
        fin_v = "REVIEW"
    else:
        fin_v = "VERIFIED"
    if disagreements and fin_v == "VERIFIED":
        fin_v = "REVIEW"
    if con_flags and fin_v == "VERIFIED" and (val or {}).get("verdict_suggestion") != "VERIFIED":
        fin_v = "REVIEW"

    return {
        "facility": n,
        "deterministic": det,
        "extractor": ext,
        "validator": val,
        "combined_trust_0_1": round(max(0.0, min(1.0, combined)), 3),
        "final_verdict": fin_v,
        "disagreements": disagreements,
        "all_flags": det_flags + con_flags,
    }


@mlflow.trace(name="trust_scorer_node", span_type="AGENT")
def trust_scorer_node(state: AgentState) -> dict:
    corr = (state.get("correlation_id") or "") or ""
    facilities = query_vector_search(state["query"], num_results=15)
    determ = [facility_dict_to_trust(f) for f in facilities if isinstance(f, dict)]

    payload = json.dumps(facilities, default=str, indent=2)[:50000]
    ext_raw = query_llm(EXTRACTOR_PROMPT, payload, max_tokens=2048)
    extracted = _parse_json_array(ext_raw) or []

    by_name: dict[str, dict] = {}
    for e in extracted:
        nm = str(e.get("name") or "").strip() or "?"
        by_name[nm] = e

    val_in = {
        "facilities": facilities,
        "pass1": extracted,
        "deterministic": determ,
    }
    val_raw = query_llm(VALIDATOR_PROMPT, json.dumps(val_in, default=str)[:50000], max_tokens=2048)
    validated = _parse_json_array(val_raw) or []
    v_by_name: dict[str, dict] = {}
    for v in validated:
        nm = str(v.get("name") or "").strip() or "?"
        v_by_name[nm] = v

    # Align rows: prefer same order as facilities
    per_fac: list[dict] = []
    for i, fac in enumerate(facilities):
        if not isinstance(fac, dict):
            continue
        name = str(fac.get("name") or f"?_{i}")
        det = next((d for d in determ if d.get("facility") == name), None)
        if not det and i < len(determ):
            det = determ[i]
        if not det:
            det = {"facility": name, "prior_0_1": 0.5, "adjusted_0_1": 0.5, "flags": [], "evidence_snippet": ""}
        ext = by_name.get(name) or (extracted[i] if i < len(extracted) else None)
        val = v_by_name.get(name) or (validated[i] if i < len(validated) else None)
        per_fac.append(_merge_row(det, ext, val))

    artifacts: dict = {
        "per_facility": per_fac,
        "extractor_raw_ok": bool(extracted),
        "validator_raw_ok": bool(validated),
        "summary": {
            "n": len(per_fac),
            "suspicious": sum(1 for r in per_fac if r.get("final_verdict") == "SUSPICIOUS"),
            "review": sum(1 for r in per_fac if r.get("final_verdict") == "REVIEW"),
            "top_contradiction_reasons": _top_reasons(per_fac, 5),
        },
    }

    # Render Markdown + embedded JSON for humans
    lines: list[str] = [
        "### Trust pipeline (Pass1 extractor → Pass2 validator + deterministic rules)",
        "",
        "| Facility | Deterministic | Combined | Verdict | Top flags |",
        "|---|---:|---:|---|---|",
    ]
    for r in per_fac[:15]:
        d_adj = (r.get("deterministic") or {}).get("adjusted_0_1", "—")
        flags = ", ".join((r.get("all_flags") or [])[:2]) or "—"
        lines.append(
            f"| {r.get('facility','?')[:60]} | {d_adj} | {r.get('combined_trust_0_1')} | "
            f"{r.get('final_verdict')} | {flags[:120]} |"
        )
    lines += [
        "",
        "<!-- trust_artifacts_json",
        json.dumps(artifacts, default=str)[:200000],
        "-->",
    ]
    analysis = "\n".join(lines)
    cits: list[dict] = []
    for r in per_fac[:20]:
        ev = (r.get("deterministic") or {}).get("evidence_snippet", "")
        cits.append(
            normalize_citation(
                source="trust_scorer",
                facility=str(r.get("facility", ""))[:200],
                field="trust",
                evidence_snippet=str(ev)[:2000],
                confidence=float(r.get("combined_trust_0_1", 0) or 0.0),
                row_id="",
                correlation_id=corr,
            )
        )
    cits.append(
        {
            "source": "trust_scorer",
            "field": "run",
            "evidence_snippet": f"analyzed {len(facilities)} facilities",
            "confidence": 0.7,
            "correlation_id": corr,
        }
    )
    return {
        "trust_result": analysis,
        "trust_artifacts": artifacts,
        "citations": cits,
    }


def _top_reasons(rows: list[dict], n: int) -> list[dict]:
    from collections import Counter

    c: Counter[str] = Counter()
    for r in rows:
        for f in (r.get("all_flags") or []):
            t = (f or "").strip()[:200]
            if t:
                c[t] += 1
    return [{"reason": a, "count": b} for a, b in c.most_common(n)]
