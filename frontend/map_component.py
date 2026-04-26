"""Folium map for India: desert/coverage overlays, HeatMap density, plugins.

Features:
  - Proportional circles (radius scales with desert-PIN count per state)
  - HeatMap layer (scattered synthetic points per state for density visualization)
  - Fullscreen + MiniMap plugins
  - Optional map center / zoom for PIN spotlight mode
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any

import folium
from folium.plugins import Fullscreen, HeatMap, MarkerCluster, MiniMap

from state_centroids import INDIA_CENTER, INDIA_STATE_CENTROIDS, INDIA_ZOOM


def _stable_rng(state_name: str) -> random.Random:
    h = hashlib.md5(state_name.encode("utf-8")).hexdigest()
    seed = int(h[:12], 16) % (2**32)
    return random.Random(seed)


def scatter_points_in_state(state_name: str, n_points: int, spread_deg: float = 1.2) -> list[tuple[float, float, float]]:
    """Return [lat, lon, weight] tuples scattered around the state centroid."""
    c = INDIA_STATE_CENTROIDS.get(state_name)
    if not c or n_points <= 0:
        return []
    base_lat, base_lon = float(c[0]), float(c[1])
    rng = _stable_rng(state_name)
    out: list[tuple[float, float, float]] = []
    for _ in range(n_points):
        dlat = rng.uniform(-spread_deg, spread_deg) * 0.6
        dlon = rng.uniform(-spread_deg, spread_deg) * 0.6
        w = 0.3 + rng.random() * 0.7
        out.append((base_lat + dlat, base_lon + dlon, w))
    return out


def desert_radius_m(pin_count: int) -> float:
    """Circle radius scales with desert severity (PIN count proxy)."""
    pc = max(0, int(pin_count))
    return min(80_000.0 + 15_000.0 * math.sqrt(pc + 1), 300_000.0)


def covered_radius_m() -> float:
    return 120_000.0


def desert_states_from_names(
    names: list[str],
    specialty: str,
    pin_counts: dict[str, int] | None = None,
    default_radius_m: float = 130_000,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pin_counts = pin_counts or {}
    for name in names or []:
        c = INDIA_STATE_CENTROIDS.get(name)
        if not c:
            continue
        pc = int(pin_counts.get(name, 0))
        r = desert_radius_m(pc) if pc > 0 else default_radius_m
        out.append({
            "state": name, "lat": c[0], "lon": c[1],
            "specialty": specialty, "radius_m": r, "pin_count": pc,
        })
    return out


def covered_states_from_names(
    names: list[str],
    specialty: str,
    radius_m: int | None = None,
) -> list[dict[str, Any]]:
    r = float(radius_m) if radius_m is not None else covered_radius_m()
    out: list[dict[str, Any]] = []
    for name in names or []:
        c = INDIA_STATE_CENTROIDS.get(name)
        if not c:
            continue
        out.append({
            "state": name, "lat": c[0], "lon": c[1],
            "specialty": specialty, "radius_m": r, "pin_count": 0,
        })
    return out


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
    bg = "#dc2626" if is_desert else "#16a34a"
    border = "#991b1b" if is_desert else "#15803d"
    abbr = name[:3].upper()
    return (
        f"<div style='background:{bg};color:#fff;border:2px solid {border};"
        f"border-radius:50%;width:28px;height:28px;line-height:28px;"
        f"text-align:center;font-size:9px;font-weight:700;box-shadow:0 1px 4px rgba(0,0,0,.4);'>"
        f"{abbr}</div>"
    )


_VERDICT_COLOR = {
    "VERIFIED": ("#15803d", "#22c55e", "✓"),
    "REVIEW":   ("#b45309", "#fbbf24", "⚠"),
    "SUSPICIOUS": ("#991b1b", "#ef4444", "✗"),
}


def _trust_pin_html(verdict: str, score: float) -> str:
    border, bg, sym = _VERDICT_COLOR.get(verdict, ("#6b7280", "#94a3b8", "?"))
    pct = int(score * 100)
    return (
        f"<div style='background:{bg};color:#fff;border:2px solid {border};"
        f"border-radius:50%;width:30px;height:30px;line-height:30px;"
        f"text-align:center;font-size:11px;font-weight:800;"
        f"box-shadow:0 2px 6px rgba(0,0,0,.5);' title='{verdict} {pct}%'>"
        f"{sym}</div>"
    )


def build_hotspot_heatmap(covered: list[dict[str, Any]], spread_deg: float = 1.0) -> list[tuple[float, float, float]]:
    """Generate heatmap points from covered states to show specialty supply concentration."""
    pts: list[tuple[float, float, float]] = []
    for d in covered or []:
        lat, lon = d.get("lat"), d.get("lon")
        if lat is None or lon is None:
            continue
        state = d.get("state", "")
        rng = _stable_rng(state + "hotspot")
        n_pts = 18
        for _ in range(n_pts):
            dlat = rng.uniform(-spread_deg, spread_deg) * 0.5
            dlon = rng.uniform(-spread_deg, spread_deg) * 0.5
            pts.append((float(lat) + dlat, float(lon) + dlon, 0.6 + rng.random() * 0.4))
    return pts


def create_india_map(
    facilities: list[dict[str, Any]] | None = None,
    desert_states: list[dict[str, Any]] | None = None,
    covered_states: list[dict[str, Any]] | None = None,
    use_clustering: bool = True,
    specialty: str = "",
    heatmap_desert_points: list[tuple[float, float, float]] | None = None,
    heatmap_hotspot_points: list[tuple[float, float, float]] | None = None,
    trust_pins: list[dict[str, Any]] | None = None,
    map_center: tuple[float, float] | None = None,
    zoom_start: int | None = None,
    spotlight: dict[str, Any] | None = None,
) -> folium.Map:
    """Folium map: circles + optional HeatMap + fullscreen + minimap + PIN spotlight.

    spotlight: { "label": str, "lat": float, "lon": float, "html": str }
    """
    loc = [map_center[0], map_center[1]] if map_center else [INDIA_CENTER[0], INDIA_CENTER[1]]
    z = int(zoom_start) if zoom_start is not None else INDIA_ZOOM

    m = folium.Map(location=loc, zoom_start=z, tiles="CartoDB positron")

    # HeatMap density (desert pressure)
    if heatmap_desert_points:
        hm = HeatMap(
            heatmap_desert_points,
            name="Desert density (heat)",
            min_opacity=0.35,
            max_zoom=10,
            radius=28,
            blur=22,
            gradient={0.2: "yellow", 0.5: "orange", 0.8: "red", 1.0: "darkred"},
        )
        hm.add_to(m)

    # HeatMap — specialty supply concentration / hotspot view
    if heatmap_hotspot_points:
        hm_hot = HeatMap(
            heatmap_hotspot_points,
            name="Specialty supply concentration (hotspot)",
            min_opacity=0.35,
            max_zoom=10,
            radius=30,
            blur=24,
            gradient={0.2: "#bfdbfe", 0.5: "#3b82f6", 0.8: "#1d4ed8", 1.0: "#1e3a8a"},
        )
        hm_hot.add_to(m)

    # Trust-verified facility pins from last triage run
    if trust_pins:
        tp_group = folium.FeatureGroup(name="Trust-verified facilities (last triage)", show=True)
        for tp in trust_pins:
            lat, lon = tp.get("lat"), tp.get("lon")
            if lat is None or lon is None:
                continue
            verdict = str(tp.get("verdict", "REVIEW"))
            score = float(tp.get("score", 0.5))
            name = str(tp.get("name", "Facility"))
            flags = tp.get("flags") or []
            flag_html = "".join(f"<br>⚠ {f[:80]}" for f in flags[:3])
            border, bg, sym = _VERDICT_COLOR.get(verdict, ("#6b7280", "#94a3b8", "?"))
            popup_html = (
                f"<div style='min-width:200px;font-family:sans-serif;'>"
                f"<b style='font-size:13px;'>{name}</b><br>"
                f"<span style='color:{border};font-weight:700;'>{sym} {verdict}</span>"
                f" &nbsp; Trust: <b>{int(score*100)}%</b>"
                f"{flag_html}"
                f"</div>"
            )
            folium.Marker(
                location=[float(lat), float(lon)],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{sym} {name[:50]} — {verdict} ({int(score*100)}%)",
                icon=folium.DivIcon(
                    html=_trust_pin_html(verdict, score),
                    icon_size=(30, 30),
                    icon_anchor=(15, 15),
                ),
            ).add_to(tp_group)
        tp_group.add_to(m)

    if covered_states:
        cov_group = folium.FeatureGroup(name="Covered states (has facilities)", show=True)
        for d in covered_states:
            lat, lon = d.get("lat"), d.get("lon")
            if lat is None or lon is None:
                continue
            spec = d.get("specialty") or specialty or "—"
            region = d.get("state") or "—"
            r_m = float(d.get("radius_m") or covered_radius_m())
            popup_html = (
                f"<div style='min-width:220px;font-family:sans-serif;line-height:1.6'>"
                f"<b style='color:#15803d;font-size:13px;'>✓ Verified Coverage</b><br>"
                f"<b>State:</b> {region}<br>"
                f"<b>Specialty:</b> {spec.title()}<br>"
                f"<b>Status:</b> <span style='color:#15803d;'>Facilities confirmed in this state</span><br>"
                f"<b>Action:</b> Run a triage query to see trust-verified facilities here"
                f"</div>"
            )
            folium.Circle(
                location=[float(lat), float(lon)],
                radius=r_m,
                color="#15803d",
                weight=1,
                fill=True,
                fill_color="#22c55e",
                fill_opacity=0.20,
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"✓ {region} — {spec.title()} covered · click for details",
            ).add_to(cov_group)
            folium.Marker(
                location=[float(lat), float(lon)],
                icon=folium.DivIcon(
                    html=_state_marker_html(region, is_desert=False),
                    icon_size=(28, 28),
                    icon_anchor=(14, 14),
                ),
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"✓ {region} — {spec.title()} covered",
            ).add_to(cov_group)
        cov_group.add_to(m)

    if desert_states:
        desert_group = folium.FeatureGroup(name="Medical deserts — zero / low coverage", show=True)
        for d in desert_states:
            lat, lon = d.get("lat"), d.get("lon")
            if lat is None or lon is None:
                continue
            spec = d.get("specialty") or specialty or "—"
            region = d.get("state") or "—"
            pc = int(d.get("pin_count") or 0)
            r_m = float(d.get("radius_m") or desert_radius_m(pc))
            pin_txt = f"~{pc} desert PINs identified" if pc > 0 else "No verified facilities found"
            popup_html = (
                f"<div style='min-width:240px;font-family:sans-serif;line-height:1.6'>"
                f"<b style='color:#dc2626;font-size:13px;'>⚠ Medical Desert</b><br>"
                f"<b>State:</b> {region}<br>"
                f"<b>Specialty:</b> {spec.title()}<br>"
                f"<b>Coverage:</b> <span style='color:#dc2626;'>Zero verified {spec} facilities</span><br>"
                f"<b>Desert PINs:</b> {pin_txt}<br>"
                f"<b>Risk:</b> Patients must travel out-of-state for this specialty<br>"
                f"<b>Action:</b> Priority zone for NGO resource deployment"
                f"</div>"
            )
            folium.Circle(
                location=[float(lat), float(lon)],
                radius=r_m,
                color="#991b1b",
                weight=1.5,
                fill=True,
                fill_color="#ef4444",
                fill_opacity=0.28,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"⚠ {region} — {spec.title()} DESERT · {pin_txt} · click for details",
            ).add_to(desert_group)
            folium.Marker(
                location=[float(lat), float(lon)],
                icon=folium.DivIcon(
                    html=_state_marker_html(region, is_desert=True),
                    icon_size=(28, 28),
                    icon_anchor=(14, 14),
                ),
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"⚠ {region} — {spec.title()} desert",
            ).add_to(desert_group)
        desert_group.add_to(m)

    if spotlight and spotlight.get("lat") is not None and spotlight.get("lon") is not None:
        sp = folium.FeatureGroup(name="PIN spotlight", show=True)
        slat, slon = float(spotlight["lat"]), float(spotlight["lon"])
        folium.Circle(
            location=[slat, slon],
            radius=45_000,
            color="#2563eb",
            weight=2,
            fill=True,
            fill_color="#3b82f6",
            fill_opacity=0.12,
        ).add_to(sp)
        folium.Marker(
            location=[slat, slon],
            popup=folium.Popup(spotlight.get("html", spotlight.get("label", "PIN")), max_width=320),
            icon=folium.Icon(color="blue", icon="info-sign"),
            tooltip=spotlight.get("label", "PIN"),
        ).add_to(sp)
        sp.add_to(m)

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

    try:
        MiniMap(tile_layer="CartoDB positron", zoom_level_offset=-4).add_to(m)
    except Exception:
        pass
    try:
        Fullscreen(position="topright", title="Fullscreen", title_cancel="Exit").add_to(m)
    except Exception:
        pass
    folium.LayerControl(collapsed=False).add_to(m)
    return m
