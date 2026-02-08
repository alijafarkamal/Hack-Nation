"""Folium map builder — renders Ghana healthcare facilities on an interactive map.

Creates a Folium map centered on Ghana with:
  - Color-coded facility markers (hospital=blue, clinic=green, etc.)
  - MarkerCluster for performance with many facilities
  - Medical desert overlay (translucent red circles for coverage gaps)
  - Popup details for each facility

Used in the Streamlit app's Map tab.
"""

import folium
from folium.plugins import MarkerCluster

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
    m = folium.Map(location=GHANA_CENTER, zoom_start=GHANA_ZOOM, tiles="CartoDB positron")

    # Add facility markers (clustered for performance)
    if facilities:
        cluster = MarkerCluster(name="Facilities").add_to(m)
        for f in facilities:
            lat = f.get("lat")
            lon = f.get("lon")
            if lat is None or lon is None:
                continue

            ftype = f.get("facilityTypeId", "doctor")
            color = FACILITY_COLORS.get(ftype, "gray")
            name = f.get("name", "Unknown")
            city = f.get("address_city", "—")
            region = f.get("region_normalized", "—")

            popup_html = (
                f"<div style='min-width:200px'>"
                f"<b>{name}</b><br>"
                f"<i>{ftype}</i><br>"
                f"City: {city}<br>"
                f"Region: {region}"
                f"</div>"
            )

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=name,
                icon=folium.Icon(color=color, icon="plus-sign"),
            ).add_to(cluster)

    # Add medical desert overlay (translucent red circles)
    if desert_regions:
        desert_group = folium.FeatureGroup(name="Medical Deserts").add_to(m)
        for d in desert_regions:
            lat = d.get("lat")
            lon = d.get("lon")
            if lat is None or lon is None:
                continue

            folium.Circle(
                location=[lat, lon],
                radius=60000,  # 60km radius
                color="#d32f2f",
                weight=2,
                fill=True,
                fill_color="#d32f2f",
                fill_opacity=0.12,
                popup=f"<b>Medical Desert</b><br>{d.get('specialty', '—')}<br>Region: {d.get('region', '—')}",
                tooltip=f"Desert: {d.get('region', '—')} ({d.get('specialty', '—')})",
            ).add_to(desert_group)

    # Layer control toggle
    folium.LayerControl().add_to(m)

    return m
