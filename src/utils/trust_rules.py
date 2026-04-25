"""Deterministic capability vs evidence checks (non-LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_LOWERS = re.compile(r"\W+")


def _norm_text(s: str | None) -> str:
    if not s or not isinstance(s, str):
        return ""
    return _LOWERS.sub(" ", s.lower()).strip()


def _jsonish_to_blob(raw: str | None) -> str:
    if not raw:
        return ""
    s = str(raw)
    if s in ("[]", "null", "None", ""):
        return ""
    return _norm_text(s)


@dataclass
class TrustRuleResult:
    """Result of running deterministic rules on one facility record."""

    facility_name: str
    adjusted_score_0_1: float
    prior_0_1: float
    flags: list[str] = field(default_factory=list)
    evidence_snippet: str = ""
    deterministic_verdict: str = "REVIEW"  # VERIFIED | SUSPICIOUS | REVIEW


def _parse_float(x: Any) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
        if 0.0 <= v <= 1.0:
            return v
        if v > 1.0:  # trust_score 0-100
            return v / 100.0
        return v
    except (TypeError, ValueError):
        return None


def _text_has_any_of(blob: str, *needles: str) -> bool:
    if not blob:
        return False
    return any(n in blob for n in needles)


def apply_deterministic_trust(facility: dict[str, Any]) -> TrustRuleResult:
    """Run rule-based trust adjustment on a single facility row."""
    name = str(facility.get("name") or "?")
    trust_raw = facility.get("trust_score")
    prior = _parse_float(trust_raw) or 0.5
    score = max(0.0, min(1.0, prior))
    flags: list[str] = []
    spec = _jsonish_to_blob(facility.get("specialties"))
    proc = _jsonish_to_blob(facility.get("procedure"))
    equip = _jsonish_to_blob(facility.get("equipment"))
    capb = _jsonish_to_blob(facility.get("capability"))
    desc = _norm_text(facility.get("description") or "")
    blob = f"{spec} {proc} {equip} {capb} {desc}"

    # Surgery / advanced without anesthesia signal
    surgery_hint = any(
        k in blob
        for k in (
            "surgery",
            "surgical",
            "operating",
            "appendectomy",
            "cesarean",
            "laparos",
        )
    )
    if surgery_hint and not any(
        k in blob for k in ("anesthesi", "anesthesia", "anaesth", "ot ", " o.t")
    ):
        if not _text_has_any_of(equip, "surgical", "ot", "theatre", "anesthesia", "c-arm"):
            flags.append("Claims surgery/OT context but no clear anesthesia/OT support in text")
            score *= 0.7

    # ICU / critical without ventilator / monitor
    icu = any(
        k in blob for k in ("icu", "intensive", "ventilator", "critical care", " nicu")
    ) or "icu" in spec
    if icu and "ventilat" not in blob and "monitor" not in blob:
        if "ventilat" not in blob:
            flags.append("ICU/critical care implied; ventilator/monitor not evidenced in text")
            score *= 0.75

    # Advanced cardiac center vs trivial equipment
    if "cardiac" in desc or "heart" in spec:
        if equip and "stethoscope" in equip and len(equip) < 40:
            flags.append("Cardiac service claim with very sparse equipment listing")
            score *= 0.65

    # Sparse evidence
    if (not spec or spec == "[]") and (not proc or proc == "[]") and (not capb or capb == "[]"):
        if len(desc) < 30:
            flags.append("Very sparse structured + unstructured evidence")
            score *= 0.85

    # Evidence sentence for UI
    evidence_snippet = (
        (desc[:180] + "…")
        if desc
        else (proc[:120] + "…" if proc else (equip[:120] if equip else "No excerpt"))
    )
    if flags:
        verdict = "SUSPICIOUS" if score < 0.45 else "REVIEW" if score < 0.65 else "VERIFIED"
    else:
        verdict = "VERIFIED" if score >= 0.65 else "REVIEW"
    return TrustRuleResult(
        facility_name=name,
        adjusted_score_0_1=round(max(0.0, min(1.0, score)), 3),
        prior_0_1=round(prior, 3),
        flags=flags,
        evidence_snippet=evidence_snippet,
        deterministic_verdict=verdict,
    )


def facility_dict_to_trust(facility: dict[str, Any]) -> dict[str, Any]:
    """Run rules and return a JSON-serializable record."""
    r = apply_deterministic_trust(facility)
    return {
        "facility": r.facility_name,
        "prior_0_1": r.prior_0_1,
        "adjusted_0_1": r.adjusted_score_0_1,
        "flags": r.flags,
        "evidence_snippet": r.evidence_snippet[:500],
        "deterministic_verdict": r.deterministic_verdict,
    }
