"""Folium map builder — renders Ghana healthcare facilities on an interactive map.

Creates a Folium map centered on Ghana with:
  - Color-coded facility markers (hospital=blue, clinic=green, etc.)
  - MarkerCluster for performance with 987+ facilities
  - Medical desert overlay (translucent red circles for coverage gaps)
  - Layer control to toggle facility types and desert overlay
  - Legend showing facility type colors

Used in the Streamlit app's Map tab.
"""

import folium
from folium.plugins import MarkerCluster

# Ghana center coordinates
GHANA_CENTER = [7.9465, -1.0232]
GHANA_ZOOM = 7

# All markers use the same dark-blue color so they don't clash with
# MarkerCluster colors (green = few, yellow = medium, orange = many).
# Facility types are distinguished by icon shape instead.
FACILITY_COLORS = {
    "hospital": "darkblue",
    "clinic": "darkblue",
    "pharmacy": "darkblue",
    "dentist": "darkblue",
    "doctor": "darkblue",
}

# Friendly labels
FACILITY_LABELS = {
    "hospital": "Hospital",
    "clinic": "Clinic",
    "pharmacy": "Pharmacy",
    "dentist": "Dentist",
    "doctor": "Doctor",
}

# Icon names for each type
FACILITY_ICONS = {
    "hospital": "plus-sign",
    "clinic": "heart",
    "pharmacy": "shopping-cart",
    "dentist": "tooth",
    "doctor": "user",
}


def _build_popup_html(f: dict) -> str:
    """Build an HTML popup for a facility marker."""
    import json as _json

    name = f.get("name", "Unknown")
    ftype = FACILITY_LABELS.get(f.get("facilityTypeId", ""), f.get("facilityTypeId", "—"))
    city = f.get("address_city", "—")
    region = f.get("region_normalized", "—")

    # Parse specialties for display
    specs_raw = f.get("specialties", "[]")
    if isinstance(specs_raw, str):
        try:
            specs = _json.loads(specs_raw)
        except (ValueError, TypeError):
            specs = []
    elif isinstance(specs_raw, list):
        specs = specs_raw
    else:
        specs = []

    specs_display = ", ".join(specs[:5]) if specs else "—"
    if len(specs) > 5:
        specs_display += f" (+{len(specs) - 5} more)"

    html = (
        f"<div style='min-width:200px; font-family:sans-serif;'>"
        f"<b style='font-size:14px;'>{name}</b><br>"
        f"<span style='color:#555;'>{ftype}</span><br>"
        f"<hr style='margin:4px 0;'>"
        f"<b>City:</b> {city}<br>"
        f"<b>Region:</b> {region}<br>"
        f"<b>Specialties:</b> {specs_display}"
        f"</div>"
    )
    return html


def create_ghana_map(
    facilities: list[dict] | None = None,
    desert_regions: list[dict] | None = None,
    use_clustering: bool = True,
) -> folium.Map:
    """Create a Folium map of Ghana with facility markers and desert overlays.

    Args:
        facilities: List of facility dicts with 'name', 'lat', 'lon',
                    'facilityTypeId', 'specialties', etc.
        desert_regions: List of dicts with 'region', 'lat', 'lon', 'specialty'
                       for medical desert overlay circles.
        use_clustering: If True, group nearby markers into clusters for
                       performance (recommended for 500+ facilities).

    Returns:
        folium.Map object ready to render in Streamlit via st_folium.
    """
    m = folium.Map(
        location=GHANA_CENTER,
        zoom_start=GHANA_ZOOM,
        tiles="OpenStreetMap",
    )

    # -- Facility markers --
    if facilities:
        if use_clustering:
            cluster = MarkerCluster(name="Facilities", show=True)
            for f in facilities:
                lat = f.get("lat")
                lon = f.get("lon")
                if lat is None or lon is None:
                    continue

                ftype = f.get("facilityTypeId", "doctor")
                color = FACILITY_COLORS.get(ftype, "gray")
                icon_name = FACILITY_ICONS.get(ftype, "info-sign")
                popup_html = _build_popup_html(f)

                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=320),
                    tooltip=f.get("name", ""),
                    icon=folium.Icon(color=color, icon=icon_name),
                ).add_to(cluster)

            cluster.add_to(m)
        else:
            for f in facilities:
                lat = f.get("lat")
                lon = f.get("lon")
                if lat is None or lon is None:
                    continue

                ftype = f.get("facilityTypeId", "doctor")
                color = FACILITY_COLORS.get(ftype, "gray")
                icon_name = FACILITY_ICONS.get(ftype, "info-sign")
                popup_html = _build_popup_html(f)

                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=320),
                    tooltip=f.get("name", ""),
                    icon=folium.Icon(color=color, icon=icon_name),
                ).add_to(m)

    # -- Medical desert overlay (translucent red circles) --
    if desert_regions:
        desert_group = folium.FeatureGroup(name="Medical Deserts", show=True)
        for d in desert_regions:
            lat = d.get("lat")
            lon = d.get("lon")
            if lat is None or lon is None:
                continue

            radius_m = d.get("radius_m", 50000)  # default 50km
            specialty = d.get("specialty", "—")
            region = d.get("region", "—")

            folium.Circle(
                location=[lat, lon],
                radius=radius_m,
                color="#e53e3e",
                weight=1,
                fill=True,
                fill_color="#e53e3e",
                fill_opacity=0.10,
                popup=folium.Popup(
                    f"<b>Medical Desert</b><br>"
                    f"<b>Specialty:</b> {specialty}<br>"
                    f"<b>Region:</b> {region}<br>"
                    f"No facilities offering {specialty} in this region.",
                    max_width=250,
                ),
                tooltip=f"Desert: {specialty} — {region}",
            ).add_to(desert_group)

        desert_group.add_to(m)

    # NOTE: LayerControl is handled by st_folium's layer_control parameter.
    # Adding it here would conflict with streamlit-folium.

    return m
