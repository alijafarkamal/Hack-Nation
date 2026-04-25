"""Confidence intervals and completeness penalties for ratios (Wilson, bootstrap-style)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WilsonInterval:
    point: float
    low: float
    high: float
    n: int = 0
    k: int = 0
    method: str = "wilson"
    confidence_notes: list[str] = field(default_factory=list)


def wilson_score_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """
    Two-sided ~95% Wilson score interval for binomial p = k/n.
    Returns (point, low, high) in [0,1]. If n=0, returns (0,0,0).
    """
    if n <= 0 or k < 0:
        return 0.0, 0.0, 0.0
    if k > n:
        k = n
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    # Wilson centre and half-width (common closed form)
    centre = (p + z2 / (2.0 * n)) / denom
    inner = p * (1.0 - p) / n + z2 / (4.0 * n * n)
    if inner < 0:
        inner = 0.0
    half = (z * math.sqrt(inner)) / denom
    lo = max(0.0, min(1.0, centre - half))
    hi = max(0.0, min(1.0, centre + half))
    return p, lo, hi


def wilson_w_interval(k: int, n: int, z: float = 1.96) -> WilsonInterval:
    p, lo, hi = wilson_score_interval(k, n, z)
    notes: list[str] = []
    if n == 0:
        notes.append("No sample (n=0); interval undefined, point 0")
    if n > 0 and n < 10:
        notes.append("Small n; use interval cautiously (n<10)")
    return WilsonInterval(
        point=p,
        low=lo,
        high=hi,
        n=n,
        k=k,
        method="wilson_95",
        confidence_notes=notes,
    )


def completeness_penalty(
    has_equipment: bool,
    has_procedure: bool,
    has_capacity: bool,
    description_len: int = 0,
) -> float:
    """
    Return multiplier in (0,1] penalising missing key structured fields.
    """
    miss = 0
    if not has_equipment:
        miss += 1
    if not has_procedure:
        miss += 1
    if not has_capacity:
        miss += 1
    if description_len < 20:
        miss += 0.5
    # exp(-0.25 * miss) in [~0.47,1]
    return max(0.4, min(1.0, math.exp(-0.25 * miss)))


def apply_penalty_to_interval(
    w: WilsonInterval, penalty: float, note: str | None = None
) -> WilsonInterval:
    """Shrink point toward 0.5 and widen [low,high] for conservative reporting."""
    p2 = 0.5 + penalty * (w.point - 0.5)
    spread = w.high - w.low
    spread2 = min(1.0, max(0.0, spread + (1.0 - penalty) * 0.15))
    mid = (w.low + w.high) / 2.0
    lo2 = max(0.0, min(1.0, mid - spread2 / 2.0))
    hi2 = max(0.0, min(1.0, mid + spread2 / 2.0))
    notes = list(w.confidence_notes)
    if note:
        notes.append(note)
    if penalty < 0.9:
        notes.append("Applied data-completeness penalty to confidence interval")
    return WilsonInterval(
        point=round(p2, 4),
        low=round(lo2, 4),
        high=round(hi2, 4),
        n=w.n,
        k=w.k,
        method=w.method + "+penalty",
        confidence_notes=notes,
    )


def ratio_dict(k: int, n: int, **penalty_args: Any) -> dict[str, Any]:
    """Helper: ratio + Wilson + optional completeness penalty (kwargs passed to completeness_penalty)."""
    w = wilson_w_interval(k, n)
    pen = 1.0
    if penalty_args:
        pen = completeness_penalty(
            bool(penalty_args.get("has_equipment", True)),
            bool(penalty_args.get("has_procedure", True)),
            bool(penalty_args.get("has_capacity", True)),
            int(penalty_args.get("description_len", 0) or 0),
        )
    if pen < 1.0:
        w = apply_penalty_to_interval(w, pen, "completeness")
    return {
        "k": k,
        "n": n,
        "point": w.point,
        "low_95": w.low,
        "high_95": w.high,
        "method": w.method,
        "confidence_notes": w.confidence_notes,
    }