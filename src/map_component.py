"""Folium map builder — renders Ghana healthcare facilities on an interactive map.

Dark-themed map inspired by VFMatch globe aesthetic with:
  - CartoDB dark_matter tiles for a space-like look
  - Glowing CircleMarkers instead of standard icons for cleaner visuals
  - MarkerCluster with custom dark styling
  - Pulsing red desert overlays for medical coverage gaps
  - Rich HTML popups with dark theme

Used in the Streamlit app's Map tab.
"""

import folium
from folium.plugins import MarkerCluster

# Ghana center coordinates
GHANA_CENTER = [7.9465, -1.0232]
GHANA_ZOOM = 7

# Glow colors by facility type (bright on dark background)
FACILITY_STYLES = {
    "hospital": {"color": "#4fc3f7", "label": "Hospital"},      # bright blue
    "clinic":   {"color": "#66bb6a", "label": "Clinic"},         # bright green
    "pharmacy": {"color": "#ffa726", "label": "Pharmacy"},       # amber
    "dentist":  {"color": "#ce93d8", "label": "Dentist"},        # light purple
    "doctor":   {"color": "#90a4ae", "label": "Doctor"},         # blue-gray
    "unknown":  {"color": "#78909c", "label": "Unknown"},        # gray
}

# Custom cluster icon style for dark theme
_CLUSTER_JS = """
function(cluster) {
    var count = cluster.getChildCount();
    var size = count < 20 ? 35 : count < 100 ? 45 : 55;
    var opacity = count < 20 ? 0.7 : count < 100 ? 0.8 : 0.9;
    return L.divIcon({
        html: '<div style="background:rgba(0,188,212,' + opacity + ');color:#fff;border-radius:50%;width:' + size + 'px;height:' + size + 'px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:13px;box-shadow:0 0 12px rgba(0,188,212,0.6);border:2px solid rgba(255,255,255,0.3);">' + count + '</div>',
        className: 'custom-cluster',
        iconSize: L.point(size, size)
    });
}
"""


def _popup_html(name: str, ftype: str, city: str, region: str, color: str) -> str:
    """Generate dark-themed popup HTML."""
    return f"""
    <div style="
        background:#1a1a2e;color:#e0e0e0;padding:12px 16px;
        border-radius:8px;min-width:220px;font-family:system-ui;
        border-left:4px solid {color};
    ">
        <div style="font-size:14px;font-weight:700;color:#fff;margin-bottom:6px;">{name}</div>
        <div style="font-size:12px;margin-bottom:3px;">
            <span style="color:{color};font-weight:600;">{ftype.title()}</span>
        </div>
        <div style="font-size:11px;color:#aaa;">
            {city} &bull; {region}
        </div>
    </div>
    """


def _desert_popup_html(region: str, specialty: str) -> str:
    """Generate desert overlay popup HTML."""
    return f"""
    <div style="
        background:#1a1a2e;color:#e0e0e0;padding:12px 16px;
        border-radius:8px;min-width:200px;font-family:system-ui;
        border-left:4px solid #ff5252;
    ">
        <div style="font-size:13px;font-weight:700;color:#ff5252;margin-bottom:4px;">
            Medical Desert
        </div>
        <div style="font-size:12px;color:#fff;">{region}</div>
        <div style="font-size:11px;color:#aaa;margin-top:2px;">
            No {specialty} coverage
        </div>
    </div>
    """


def create_ghana_map(
    facilities: list[dict] | None = None,
    desert_regions: list[dict] | None = None,
) -> folium.Map:
    """Create a dark-themed Folium map of Ghana with facility markers and desert overlays.

    Args:
        facilities: List of facility dicts with 'name', 'lat', 'lon',
                    'facilityTypeId', 'specialties' keys.
        desert_regions: List of dicts with 'region', 'lat', 'lon', 'specialty'
                       for medical desert overlay circles.

    Returns:
        folium.Map object ready to render in Streamlit.
    """
    m = folium.Map(
        location=GHANA_CENTER,
        zoom_start=GHANA_ZOOM,
        tiles=None,
        control_scale=True,
    )

    # Dark tile layer (hidden from layer control since it's the only base)
    folium.TileLayer(
        tiles="CartoDB dark_matter",
        name="Dark Map",
        attr="&copy; CartoDB",
        control=False,
    ).add_to(m)

    # Add facility markers (clustered with custom dark styling)
    if facilities:
        cluster = MarkerCluster(
            name="Facilities",
            icon_create_function=_CLUSTER_JS,
        ).add_to(m)

        for f in facilities:
            lat = f.get("lat")
            lon = f.get("lon")
            if lat is None or lon is None:
                continue

            ftype = f.get("facilityTypeId") or "unknown"
            style = FACILITY_STYLES.get(ftype, FACILITY_STYLES["unknown"])
            color = style["color"]
            name = f.get("name", "Unknown")
            city = f.get("address_city") or "—"
            region = f.get("region_normalized") or "—"

            folium.CircleMarker(
                location=[lat, lon],
                radius=7,
                color=color,
                weight=2,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                popup=folium.Popup(
                    _popup_html(name, ftype, city, region, color),
                    max_width=280,
                ),
                tooltip=f"{name} ({style['label']})",
            ).add_to(cluster)

    # Add medical desert overlay (glowing red circles)
    if desert_regions:
        desert_group = folium.FeatureGroup(name="Medical Deserts").add_to(m)
        for d in desert_regions:
            lat = d.get("lat")
            lon = d.get("lon")
            if lat is None or lon is None:
                continue

            region = d.get("region", "—")
            specialty = d.get("specialty", "—")

            # Outer glow
            folium.Circle(
                location=[lat, lon],
                radius=65000,
                color="#ff5252",
                weight=1,
                fill=True,
                fill_color="#ff5252",
                fill_opacity=0.06,
            ).add_to(desert_group)

            # Inner ring
            folium.Circle(
                location=[lat, lon],
                radius=50000,
                color="#ff5252",
                weight=2,
                dash_array="8 4",
                fill=True,
                fill_color="#ff5252",
                fill_opacity=0.12,
                popup=folium.Popup(
                    _desert_popup_html(region, specialty),
                    max_width=250,
                ),
                tooltip=f"Desert: {region} (no {specialty})",
            ).add_to(desert_group)

    # Layer control with dark-friendly styling
    folium.LayerControl(collapsed=False).add_to(m)

    return m
