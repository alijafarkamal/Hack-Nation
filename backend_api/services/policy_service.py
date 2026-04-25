"""Policy / desert aggregators: reuse geospatial + DB."""

from __future__ import annotations

from typing import Any

from src.citations import normalize_citation
from src.config import TABLE_FACILITIES
from src.nodes.geospatial import _run_facility_sql, find_desert_pins, find_desert_states
from src.utils.confidence import wilson_w_interval


def _list_facilities_minimal() -> list[dict]:
    return _run_facility_sql(
        f"SELECT name, state_normalized, pin_code, specialties, trust_score, trust_flag, "
        f"procedure, equipment, capability "
        f"FROM {TABLE_FACILITIES} WHERE state_normalized IS NOT NULL"
    )


def get_desert_report(
    specialty: str, level: str, correlation_id: str
) -> dict[str, Any]:
    fac = _list_facilities_minimal()
    st = (specialty or "").strip() or "emergency"
    d_states = find_desert_states(fac, st)
    d_pins = find_desert_pins(fac, st) if (level or "").lower() == "pin" else []
    all_pins = {str(f.get("pin_code", "")).strip() for f in fac if f.get("pin_code")}
    all_pins.discard("")
    n = len(all_pins)
    k = len(d_pins) if (level or "").lower() == "pin" else 0
    w = wilson_w_interval(int(k), int(n)) if n and (level or "").lower() == "pin" else None
    cit = [
        dict(
            normalize_citation(
                source="policy",
                facility="",
                field="desert_aggregator",
                evidence_snippet=f"Specialty={st}, n_pins={n}, k_desert={k} (Wilson when level=pin)",
                confidence=0.55 if w else 0.4,
                row_id="",
                correlation_id=correlation_id,
            )
        )
    ]
    return {
        "specialty": st,
        "level": (level or "state").lower(),
        "desert_states": d_states,
        "desert_pins": d_pins,
        "desert_state_count": len(d_states),
        "desert_pin_count": len(d_pins),
        "desert_pin_ratio_interval": (
            {
                "k": k,
                "n": n,
                "point": w.point,
                "low_95": w.low,
                "high_95": w.high,
                "method": w.method,
                "confidence_notes": w.confidence_notes,
            }
            if w
            else None
        ),
        "top_contradiction_reasons": [],
        "citations": cit,
        "safety_framing": "Policy / coverage analytics — not clinical guidance.",
        "correlation_id": correlation_id,
    }


def get_pin_risk(pin_code: str, correlation_id: str) -> dict[str, Any]:
    pin = (pin_code or "").strip()
    if not (len(pin) == 6 and pin.isdigit()):
        return {
            "error": "Invalid PIN (expect 6 digits).",
            "citations": [],
            "correlation_id": correlation_id,
        }
    rows = _run_facility_sql(
        f"SELECT name, state_normalized, pin_code, trust_score, trust_flag, "
        f"specialties, procedure, equipment, capability "
        f"FROM {TABLE_FACILITIES} WHERE pin_code = '{pin}' LIMIT 200"
    )
    n = len(rows or [])
    k_high = 0
    for f in rows or []:
        try:
            ts = f.get("trust_score")
            if ts is None:
                continue
            v = float(ts)
            if v > 1.0:
                v = v / 100.0
            if v >= 0.65:
                k_high += 1
        except (TypeError, ValueError):
            continue
    w = wilson_w_interval(int(k_high), int(n)) if n else wilson_w_interval(0, 0)
    void_reasons: list[str] = []
    for f in rows or []:
        b = (
            f"{(f.get('specialties') or '')} "
            f"{(f.get('procedure') or '')} "
            f"{(f.get('equipment') or '')}"
        ).lower()
        if b.strip() in ("", "[]", "null", "[]"):
            void_reasons.append("sparse structured text")
            break
    return {
        "pin_code": pin,
        "facility_count": n,
        "high_trust_wilson": {
            "k": k_high,
            "n": n,
            "point": w.point,
            "low_95": w.low,
            "high_95": w.high,
            "confidence_notes": w.confidence_notes
            + (["PIN has no rows in current snapshot"] if n == 0 else []),
        },
        "sample_facilities": [
            {
                "name": f.get("name"),
                "trust_score": f.get("trust_score"),
            }
            for f in (rows or [])[:8]
        ],
        "contrast_reasons": void_reasons,
        "citations": [
            dict(
                normalize_citation(
                    source="policy",
                    facility="",
                    field="pin_risk",
                    evidence_snippet=f"PIN {pin} facilities n={n}, high_trust k={k_high} (Wilson interval)",
                    confidence=0.5 if n else 0.25,
                    row_id=pin,
                    correlation_id=correlation_id,
                )
            )
        ],
        "safety_framing": "Policy / coverage analytics — not clinical guidance.",
        "correlation_id": correlation_id,
    }
