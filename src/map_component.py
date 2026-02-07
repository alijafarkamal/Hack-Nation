"""Folium map builder — renders Ghana healthcare facilities on an interactive map.

Creates a Folium map centered on Ghana with:
  - Color-coded facility markers (hospital=blue, clinic=green, etc.)
  - Medical desert overlay (translucent red circles for coverage gaps)
  - Popup details for each facility

Used in the Streamlit app's Map tab.
"""

import folium

# Ghana center coordinates
GHANA_CENTER = [7.9465, -1.0232]
GHANA_ZOOM = 7

# Marker colors by facility type
FACILITY_COLORS = {
    "hospital": "blue",
    "clinic": "green",
    "pharmacy": "orange",
    "dentist": "purple",
    "doctor": "gray",
}


def create_ghana_map(
    facilities: list[dict] | None = None,
    desert_regions: list[dict] | None = None,
) -> folium.Map:
    """Create a Folium map of Ghana with facility markers and desert overlays.

    Args:
        facilities: List of facility dicts with 'name', 'lat', 'lon',
                    'facilityTypeId', 'specialties' keys.
        desert_regions: List of dicts with 'region', 'lat', 'lon', 'specialty'
                       for medical desert overlay circles.

    Returns:
        folium.Map object ready to render in Streamlit.
    """
    m = folium.Map(location=GHANA_CENTER, zoom_start=GHANA_ZOOM)

    # Add facility markers
    if facilities:
        for f in facilities:
            lat = f.get("lat")
            lon = f.get("lon")
            if lat is None or lon is None:
                continue

            ftype = f.get("facilityTypeId", "doctor")
            color = FACILITY_COLORS.get(ftype, "gray")

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(
                    f"<b>{f.get('name', 'Unknown')}</b><br>"
                    f"Type: {ftype}<br>"
                    f"City: {f.get('address_city', '—')}<br>"
                    f"Specialties: {f.get('specialties', '—')}",
                    max_width=300,
                ),
                icon=folium.Icon(color=color, icon="plus-sign"),
            ).add_to(m)

    # Add medical desert overlay (translucent red circles)
    if desert_regions:
        for d in desert_regions:
            lat = d.get("lat")
            lon = d.get("lon")
            if lat is None or lon is None:
                continue

            folium.Circle(
                location=[lat, lon],
                radius=50000,  # 50km radius
                color="red",
                fill=True,
                fill_opacity=0.15,
                popup=f"Medical desert: {d.get('specialty', '—')} — {d.get('region', '—')}",
            ).add_to(m)

    return m
