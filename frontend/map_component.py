"""Folium map for India: facility/state markers + medical desert overlay.

Features:
  - Colour-coded markers for covered states (green) with hospital icon
  - Desert overlay: translucent amber circles for states with zero specialty coverage
  - MarkerCluster for performance with large facility lists
  - DivIcon custom markers for state-level display (named, coloured)
  - LayerControl for toggling desert vs covered layers
"""

from __future__ import annotations

from typing import Any

import folium
from folium.plugins import MarkerCluster

from state_centroids import INDIA_CENTER, INDIA_STATE_CENTROIDS, INDIA_ZOOM

DEFAULT_MARKER_COLOR = "darkred"


def _facility_popup(f: dict[str, Any]) -> str:
    name = f.get("name") or "—"
    state = f.get("state") or f.get("state_normalized") or "—"
    pin = f.get("pin") or f.get("pin_code") or "—"
    caps = f.get("capabilities_needed") or f.get("specialties") or []
    cap_str = ", ".join(caps[:5]) if isinstance(caps, list) else str(caps)
    return (
        f"<div style='min-width:220px;font-family:sans-serif;'>"
        f"<b style='font-size:14px;'>{name}</b><br>"
        f"<span style='color:#555;'>State: {state} · PIN: {pin}</span>"
        + (f"<br><span style='color:#2563eb;'>Capabilities: {cap_str}</span>" if cap_str else "")
        + "</div>"
    )


def _state_marker_html(name: str, is_desert: bool) -> str:
    """Small circular DivIcon with state abbreviation."""
    bg = "#dc2626" if is_desert else "#16a34a"
    border = "#991b1b" if is_desert else "#15803d"
    abbr = name[:3].upper()
    return (
        f"<div style='background:{bg};color:#fff;border:2px solid {border};"
        f"border-radius:50%;width:28px;height:28px;line-height:28px;"
        f"text-align:center;font-size:9px;font-weight:700;box-shadow:0 1px 4px rgba(0,0,0,.4);'>"
        f"{abbr}</div>"
    )


def create_india_map(
    facilities: list[dict[str, Any]] | None = None,
    desert_states: list[dict[str, Any]] | None = None,
    covered_states: list[dict[str, Any]] | None = None,
    use_clustering: bool = True,
    specialty: str = "",
) -> folium.Map:
    """Build Folium map centred on India with heatmap-style desert + coverage overlay.

    When desert_states and/or covered_states are provided this renders a
    choropleth-style heatmap:
      - Red filled circles  = medical deserts (zero specialty coverage)
      - Green filled circles = states with confirmed coverage
    Facility pin markers are kept on a separate layer.
    """
    m = folium.Map(
        location=[INDIA_CENTER[0], INDIA_CENTER[1]],
        zoom_start=INDIA_ZOOM,
        tiles="CartoDB positron",
    )

    # ── Heatmap circles — covered states (green) ──────────────────────────
    if covered_states:
        cov_group = folium.FeatureGroup(name="Covered states (has facilities)", show=True)
        for d in covered_states:
            lat, lon = d.get("lat"), d.get("lon")
            if lat is None or lon is None:
                continue
            spec = d.get("specialty") or specialty or "—"
            region = d.get("state") or "—"
            folium.Circle(
                location=[float(lat), float(lon)],
                radius=float(d.get("radius_m") or 120_000),
                color="#15803d",
                weight=1,
                fill=True,
                fill_color="#22c55e",
                fill_opacity=0.22,
                popup=folium.Popup(
                    f"<b style='color:#15803d;'>✓ Covered</b><br>"
                    f"<b>State:</b> {region}<br>"
                    f"<b>Specialty:</b> {spec}<br>"
                    f"Facilities offering <b>{spec}</b> detected here.",
                    max_width=260,
                ),
                tooltip=f"✓ {region} — has {spec} coverage",
            ).add_to(cov_group)
            folium.Marker(
                location=[float(lat), float(lon)],
                icon=folium.DivIcon(
                    html=_state_marker_html(region, is_desert=False),
                    icon_size=(28, 28),
                    icon_anchor=(14, 14),
                ),
                tooltip=f"✓ {region}",
            ).add_to(cov_group)
        cov_group.add_to(m)

    # ── Heatmap circles — desert states (red) ────────────────────────────
    if desert_states:
        desert_group = folium.FeatureGroup(name="Medical deserts — zero coverage", show=True)
        for d in desert_states:
            lat, lon = d.get("lat"), d.get("lon")
            if lat is None or lon is None:
                continue
            spec = d.get("specialty") or specialty or "—"
            region = d.get("state") or "—"
            folium.Circle(
                location=[float(lat), float(lon)],
                radius=float(d.get("radius_m") or 130_000),
                color="#991b1b",
                weight=1.5,
                fill=True,
                fill_color="#ef4444",
                fill_opacity=0.30,
                popup=folium.Popup(
                    f"<b style='color:#dc2626;'>⚠ Medical Desert</b><br>"
                    f"<b>State:</b> {region}<br>"
                    f"<b>Specialty:</b> {spec}<br>"
                    f"<b>Zero facilities</b> offering <b>{spec}</b> detected in this region.",
                    max_width=280,
                ),
                tooltip=f"⚠ Desert: {region} — no {spec}",
            ).add_to(desert_group)
            folium.Marker(
                location=[float(lat), float(lon)],
                icon=folium.DivIcon(
                    html=_state_marker_html(region, is_desert=True),
                    icon_size=(28, 28),
                    icon_anchor=(14, 14),
                ),
                tooltip=f"⚠ {region} — no {spec} coverage",
            ).add_to(desert_group)
        desert_group.add_to(m)

    # ── Facility pin markers (when specific facilities are passed) ────────
    facs = [f for f in (facilities or []) if not f.get("_is_desert") and f.get("pin_code") != "—"]
    with_coords: list[dict[str, Any]] = []
    for f in facs:
        lat, lon = f.get("lat"), f.get("lon")
        if lat is None or lon is None:
            continue
        try:
            with_coords.append({**f, "lat": float(lat), "lon": float(lon)})
        except (TypeError, ValueError):
            continue

    if with_coords:
        fac_group = folium.FeatureGroup(name="Matched facilities", show=True)
        if use_clustering and len(with_coords) > 10:
            cluster = MarkerCluster(name="Facilities", show=True)
            for f in with_coords:
                folium.Marker(
                    location=[f["lat"], f["lon"]],
                    popup=folium.Popup(_facility_popup(f), max_width=300),
                    tooltip=str(f.get("name", ""))[:80],
                    icon=folium.Icon(color="blue", icon="plus-sign"),
                ).add_to(cluster)
            cluster.add_to(fac_group)
        else:
            for f in with_coords:
                folium.Marker(
                    location=[f["lat"], f["lon"]],
                    popup=folium.Popup(_facility_popup(f), max_width=300),
                    tooltip=str(f.get("name", ""))[:80],
                    icon=folium.Icon(color="blue", icon="plus-sign"),
                ).add_to(fac_group)
        fac_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def desert_states_from_names(
    names: list[str],
    specialty: str,
    radius_m: int = 130_000,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in names or []:
        c = INDIA_STATE_CENTROIDS.get(name)
        if not c:
            continue
        out.append({
            "state": name, "lat": c[0], "lon": c[1],
            "specialty": specialty, "radius_m": radius_m,
        })
    return out


def covered_states_from_names(
    names: list[str],
    specialty: str,
    radius_m: int = 120_000,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in names or []:
        c = INDIA_STATE_CENTROIDS.get(name)
        if not c:
            continue
        out.append({
            "state": name, "lat": c[0], "lon": c[1],
            "specialty": specialty, "radius_m": radius_m,
        })
    return out
