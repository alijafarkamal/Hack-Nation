"""Standard citation schema for API + MLflow-friendly traces."""

from __future__ import annotations

from typing import Any, TypedDict


class CitationRecord(TypedDict, total=False):
    source: str
    facility: str
    field: str
    evidence_snippet: str
    confidence: float
    row_id: str
    correlation_id: str


def normalize_citation(
    source: str = "",
    facility: str = "",
    field: str = "",
    evidence_snippet: str = "",
    confidence: float = 0.0,
    row_id: str = "",
    correlation_id: str = "",
) -> CitationRecord:
    return CitationRecord(
        source=source,
        facility=facility,
        field=field,
        evidence_snippet=(evidence_snippet or "")[:2000],
        confidence=float(max(0.0, min(1.0, confidence))),
        row_id=row_id,
        correlation_id=correlation_id,
    )


def citations_from_list(raw: list[Any] | None, correlation_id: str = "") -> list[CitationRecord]:
    out: list[CitationRecord] = []
    for x in raw or []:
        if not isinstance(x, dict):
            continue
        d = x
        fac = d.get("facility", d.get("facility_name", d.get("name", "")))
        try:
            conf = float(d.get("confidence", 0) or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        ev = d.get("evidence_snippet") or d.get("evidence") or d.get("snippet") or ""
        out.append(
            normalize_citation(
                source=str(d.get("source", "") or "evidence"),
                facility=str(fac or ""),
                field=str(d.get("field", "") or ""),
                evidence_snippet=str(ev)[:2000],
                confidence=conf,
                row_id=str(d.get("row_id", d.get("id", "")) or ""),
                correlation_id=str(correlation_id or d.get("correlation_id", "") or ""),
            )
        )
    return out
