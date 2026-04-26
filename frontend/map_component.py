"""Folium map for India: facility markers (optional) + medical desert overlay."""

from __future__ import annotations

from typing import Any

import folium
from folium.plugins import MarkerCluster

from state_centroids import INDIA_CENTER, INDIA_STATE_CENTROIDS, INDIA_ZOOM

# Amber / saffron accent for default markers (distinct from Ghana darkblue)
DEFAULT_MARKER_COLOR = "darkred"


def _popup_html(f: dict[str, Any]) -> str:
    name = f.get("name") or "—"
    state = f.get("state") or f.get("state_normalized") or "—"
    pin = f.get("pin") or f.get("pin_code") or "—"
    return (
        f"<div style='min-width:200px;font-family:sans-serif;'>"
        f"<b style='font-size:14px;'>{name}</b><br>"
        f"<span style='color:#555;'>State: {state} · PIN: {pin}</span>"
        f"</div>"
    )


def create_india_map(
    facilities: list[dict[str, Any]] | None = None,
    desert_states: list[dict[str, Any]] | None = None,
    use_clustering: bool = True,
) -> folium.Map:
    """Build Folium map centered on India.

    facilities: items with name, lat, lon (optional; skip rows missing coords).
    desert_states: list of {state, lat, lon, radius_m?, specialty?} for red circles.
    """
    m = folium.Map(
        location=[INDIA_CENTER[0], INDIA_CENTER[1]],
        zoom_start=INDIA_ZOOM,
        tiles="OpenStreetMap",
    )

    facs = facilities or []
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
        if use_clustering and len(with_coords) > 20:
            cluster = MarkerCluster(name="Facilities", show=True)
            for f in with_coords:
                folium.Marker(
                    location=[f["lat"], f["lon"]],
                    popup=folium.Popup(_popup_html(f), max_width=300),
                    tooltip=str(f.get("name", ""))[:80],
                    icon=folium.Icon(color=DEFAULT_MARKER_COLOR, icon="plus-sign"),
                ).add_to(cluster)
            cluster.add_to(m)
        else:
            for f in with_coords:
                folium.Marker(
                    location=[f["lat"], f["lon"]],
                    popup=folium.Popup(_popup_html(f), max_width=300),
                    tooltip=str(f.get("name", ""))[:80],
                    icon=folium.Icon(color=DEFAULT_MARKER_COLOR, icon="plus-sign"),
                ).add_to(m)

    if desert_states:
        desert_group = folium.FeatureGroup(name="Medical deserts (state centroids)", show=True)
        for d in desert_states:
            lat = d.get("lat")
            lon = d.get("lon")
            if lat is None or lon is None:
                continue
            radius_m = float(d.get("radius_m") or 55_000)
            spec = d.get("specialty") or "—"
            region = d.get("state") or "—"
            folium.Circle(
                location=[float(lat), float(lon)],
                radius=radius_m,
                color="#d97706",
                weight=1,
                fill=True,
                fill_color="#f59e0b",
                fill_opacity=0.12,
                popup=folium.Popup(
                    f"<b>Desert (policy)</b><br><b>State:</b> {region}<br>"
                    f"<b>Specialty signal:</b> {spec}",
                    max_width=260,
                ),
                tooltip=f"Desert: {region}",
            ).add_to(desert_group)
        desert_group.add_to(m)

    return m


def desert_states_from_names(
    names: list[str],
    specialty: str,
    radius_m: int = 55_000,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in names or []:
        c = INDIA_STATE_CENTROIDS.get(name)
        if not c:
            continue
        out.append(
            {
                "state": name,
                "lat": c[0],
                "lon": c[1],
                "specialty": specialty,
                "radius_m": radius_m,
            }
        )
    return out
