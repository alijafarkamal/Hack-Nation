"""
Tavily-based facility contact/hours enrichment (heuristic parse; no live DB write).

Falls back with clear error if TAVILY_API_KEY is missing.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

from backend_api.integrations import get_tavily_api_key, tavily_effective
from src.citations import normalize_citation

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def _extract_phone_from_text(s: str) -> str | None:
    if not s:
        return None
    m = re.search(r"\+91[\s\-]?\d{5}[\s\-]?\d{5}", s)
    if m:
        return re.sub(r"\D", "", m.group(0)) if m.group(0) else None
    m2 = re.search(r"(?<!\d)(?:0)?[6-9]\d{9}(?!\d)", s)
    if m2:
        return "+91" + re.sub(r"\D", "", m2.group(0))[-10:]
    return None


def _extract_url(s: str) -> str | None:
    m = re.search(r"https?://[^\s)]+", s or "")
    return m.group(0).rstrip(").,;") if m else None


def _hours_hint(text: str) -> str:
    t = (text or "").lower()
    if "24/7" in t or "24x7" in t or "round the clock" in t:
        return "Hours mentioned in result text: 24/7 (not independently verified)"
    if re.search(r"\b\d{1,2}:\d{2}\b", t):
        return "Possible hours reference in text (not independently verified) — call ahead"
    return "Hours not verified from search; call ahead"


def tavily_search(q: str, num: int = 8) -> dict[str, Any] | None:
    key = get_tavily_api_key()
    if not key:
        return None
    try:
        r = requests.post(
            TAVILY_SEARCH_URL,
            headers={"Content-Type": "application/json"},
            json={
                "api_key": key,
                "query": q,
                "search_depth": "basic",
                "max_results": min(max(1, num), 20),
                "include_answer": False,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("Tavily request failed: %s", e)
        return None


def _tavily_results_to_rows(data: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize to {title, snippet, link} like legacy Serper 'organic' rows."""
    out: list[dict[str, str]] = []
    for row in (data or {}).get("results") or []:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "title": str(row.get("title", "") or ""),
                "snippet": str(row.get("content", "") or row.get("raw_content", "") or ""),
                "link": str(row.get("url", "") or ""),
            }
        )
    return out


def enrich_facility(
    facility_name: str,
    district: str = "",
    state: str = "",
    correlation_id: str = "",
) -> dict[str, Any]:
    """Search + heuristic extraction. Returns success flag and citations from result titles/content."""
    if not tavily_effective():
        return {
            "success": False,
            "error": "TAVILY_API_KEY not set; enrichment disabled",
            "query": None,
            "citations": [],
            "enrichment": {},
            "correlation_id": correlation_id,
        }
    q = f"{facility_name} hospital phone website"
    if district or state:
        q += f" {district} {state}".strip()
    q = re.sub(r"\s+", " ", q).strip()
    data = tavily_search(q, num=8)
    if not data:
        return {
            "success": False,
            "error": "Tavily request failed or empty response",
            "query": q,
            "citations": _std_cite(correlation_id, "enrichment", "tavily", q, 0.2),
            "enrichment": {},
            "correlation_id": correlation_id,
        }
    org = _tavily_results_to_rows(data)
    if not org:
        return {
            "success": False,
            "error": "Tavily returned no result rows",
            "query": q,
            "citations": _std_cite(correlation_id, "enrichment", "tavily", q, 0.2),
            "enrichment": {},
            "correlation_id": correlation_id,
        }
    phones: list[str] = []
    urls: list[str] = []
    snippets: list[str] = []
    for o in org[:8]:
        line = f"{o.get('title', '')} {o.get('snippet', '')} {o.get('link', '')}"
        snippets.append(line[:500])
        ph = _extract_phone_from_text(line)
        if ph and ph not in phones:
            phones.append(ph)
        u = o.get("link") or _extract_url(line)
        if u and u not in urls:
            urls.append(u)
    best_phone = phones[0] if phones else None
    best_url = urls[0] if urls else None
    conf = 0.35
    if best_phone and best_url:
        conf = 0.6
    elif best_phone or best_url:
        conf = 0.45
    hours = _hours_hint(" ".join(snippets)[:2000])
    cits: list[dict] = []
    for i, o in enumerate(org[:5]):
        cits.append(
            normalize_citation(
                source="tavily",
                facility=facility_name,
                field="search_hit",
                evidence_snippet=f"{(o.get('title') or '')} — {(o.get('snippet') or '')}"[:2000],
                confidence=min(0.75, 0.35 + i * 0.05),
                row_id="",
                correlation_id=correlation_id,
            )
        )
    cits.append(
        dict(
            normalize_citation(
                source="enrichment",
                facility=facility_name,
                field="disclaimer",
                evidence_snippet="Heuristic phone/URL parse from web search; verify before use",
                confidence=0.3,
                row_id="",
                correlation_id=correlation_id,
            )
        )
    )
    return {
        "success": True,
        "error": None,
        "query": q,
        "raw_organic_count": len(org),
        "enrichment": {
            "phone_estimated": best_phone,
            "website_estimated": best_url,
            "all_phones": phones[:5],
            "all_websites": urls[:5],
            "hours_note": hours,
            "confidence_0_1": round(conf, 2),
        },
        "citations": [dict(c) for c in cits],
        "correlation_id": correlation_id,
    }


def _std_cite(
    correlation_id: str, src: str, field: str, ev: str, conf: float
) -> list[dict]:
    return [
        dict(
            normalize_citation(
                source=src,
                facility="",
                field=field,
                evidence_snippet=ev[:2000],
                confidence=conf,
                row_id="",
                correlation_id=correlation_id,
            )
        )
    ]


def enrich_batch(
    items: list[dict[str, str]], correlation_id: str
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items[:20]:
        name = (it.get("name") or it.get("facility_name") or "").strip() or "Unknown"
        out.append(
            enrich_facility(
                name,
                (it.get("district") or "").strip(),
                (it.get("state") or "").strip(),
                correlation_id=correlation_id,
            )
        )
    return out
