"use client";

import { useEffect, useMemo, useState } from "react";
import { divIcon, latLngBounds } from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, useMap, ZoomControl } from "react-leaflet";
import type { Facility } from "@/lib/facilities";

const colors = { VERIFIED: "#13b981", REVIEW: "#f59e0b", SUSPICIOUS: "#ef476f" };

export default function MapPanel({ facilities, selectedId, onSelect }: {
  facilities: Facility[]; selectedId?: string; onSelect: (facility: Facility) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const mapped = useMemo(() => facilities.filter(f => f.latitude != null && f.longitude != null), [facilities]);
  const coordinateKey = mapped.map(f => `${f.id}:${f.latitude}:${f.longitude}`).join("|");

  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setExpanded(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);

  return <div className={`map-shell triage-light-map${expanded ? " map-fullscreen" : ""}`}>
    <MapContainer center={[22.8, 79.2]} zoom={5} zoomControl={false} scrollWheelZoom className="leaflet-map">
      <TileLayer
        attribution="&copy; OpenStreetMap contributors &copy; CARTO"
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        maxZoom={19}
      />
      <ZoomControl position="bottomright" />
      <MapViewport facilities={mapped} coordinateKey={coordinateKey} expanded={expanded} />
      {mapped.map((facility, index) => <Marker
        key={facility.id}
        position={[facility.latitude!, facility.longitude!]}
        icon={facilityIcon(index + 1, colors[facility.verdict], facility.id === selectedId)}
        zIndexOffset={facility.id === selectedId ? 1000 : index}
        eventHandlers={{ click: () => onSelect(facility) }}
      ><Popup><strong>{index + 1}. {facility.name}</strong><br/>{facility.state}<br/>{facility.verdict} · {Math.round(facility.score * 100)}%</Popup></Marker>)}
    </MapContainer>
    {!mapped.length && <div className="map-empty"><b>No exact coordinates returned</b><span>Results remain available in the evidence list.</span></div>}
    <div className="map-legend"><b>Facility status</b><span><i className="dot verified"/>Verified match</span><span><i className="dot review"/>Needs review</span><span><i className="dot suspicious"/>Insufficient evidence</span></div>
    <button className="map-expand" type="button" onClick={() => setExpanded(value => !value)}>{expanded ? "Close full map ✕" : "View full map ⛶"}</button>
  </div>;
}

function MapViewport({ facilities, coordinateKey, expanded }: { facilities: Facility[]; coordinateKey: string; expanded: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (facilities.length === 1) map.setView([facilities[0].latitude!, facilities[0].longitude!], 12, { animate: false });
    else if (facilities.length > 1) map.fitBounds(latLngBounds(facilities.map(f => [f.latitude!, f.longitude!])), { padding: [50, 50], maxZoom: 12, animate: false });
  // coordinateKey is the stable data identity; selection does not refit the map.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coordinateKey, map]);
  useEffect(() => { const timer=window.setTimeout(()=>map.invalidateSize({animate:false}),80);return()=>window.clearTimeout(timer); }, [expanded, map]);
  return null;
}

function facilityIcon(rank: number, color: string, selected: boolean) {
  return divIcon({
    className: "facility-pin-wrap",
    html: `<span class="facility-pin${selected ? " selected" : ""}" style="--pin:${color}"><b>${rank}</b></span>`,
    iconSize: [34, 43], iconAnchor: [17, 41], popupAnchor: [0, -38],
  });
}
