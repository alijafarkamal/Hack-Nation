"use client";

import { useEffect, useMemo, useState } from "react";
import { divIcon, latLngBounds } from "leaflet";
import { MapContainer, Marker, Popup, TileLayer, useMap, ZoomControl } from "react-leaflet";
import type { Facility } from "@/lib/facilities";

const colors = { VERIFIED: "#10B981", REVIEW: "#F59E0B", SUSPICIOUS: "#F43F5E" };

export default function MapPanel({ facilities, selectedId, onSelect }: {
  facilities: Facility[]; selectedId?: string; onSelect: (facility: Facility) => void;
}) {
  const mapped = useMemo(() => facilities.filter(f => f.latitude != null && f.longitude != null), [facilities]);
  const coordinateKey = mapped.map(f => `${f.id}:${f.latitude}:${f.longitude}`).join("|");

  return (
    <>
      <MapContainer center={[22.8, 79.2]} zoom={5} zoomControl={false} scrollWheelZoom className="leaflet-map">
        <TileLayer
          attribution="&copy; OpenStreetMap &copy; CARTO"
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          maxZoom={19}
        />
        <ZoomControl position="bottomleft" />
        <MapViewport facilities={mapped} coordinateKey={coordinateKey} />
        {mapped.map((facility, index) => (
          <Marker
            key={facility.id}
            position={[facility.latitude!, facility.longitude!]}
            icon={facilityIcon(colors[facility.verdict], facility.id === selectedId)}
            zIndexOffset={facility.id === selectedId ? 1000 : index}
            eventHandlers={{ click: () => onSelect(facility) }}
          >
            <Popup>
              <div className="vc-popup-name">{facility.name}</div>
              <div className="vc-popup-addr">{[facility.city, facility.state, facility.pin].filter(Boolean).join(", ")}</div>
              <div className="vc-popup-caps">Trust Score: {Math.round(facility.score * 100)}% · {facility.verdict}</div>
              {facility.capabilities.slice(0, 3).length > 0 && (
                <div className="vc-popup-type">{facility.capabilities.slice(0, 3).map(c => c.replace(/([A-Z])/g, " $1").trim()).join(", ")}</div>
              )}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      <div className="vc-map-legend">
        <div><span className="vc-dot" style={{ background: "#10B981" }}></span>Verified Match</div>
        <div><span className="vc-dot" style={{ background: "#F59E0B" }}></span>Needs Review</div>
        <div><span className="vc-dot" style={{ background: "#F43F5E" }}></span>Suspicious</div>
      </div>
    </>
  );
}

function MapViewport({ facilities, coordinateKey }: { facilities: Facility[]; coordinateKey: string; }) {
  const map = useMap();
  useEffect(() => {
    if (facilities.length === 1) map.setView([facilities[0].latitude!, facilities[0].longitude!], 12, { animate: false });
    else if (facilities.length > 1) map.fitBounds(latLngBounds(facilities.map(f => [f.latitude!, f.longitude!])), { padding: [50, 50], maxZoom: 12, animate: false });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coordinateKey, map]);
  useEffect(() => { const timer=window.setTimeout(()=>map.invalidateSize({animate:false}),80);return()=>window.clearTimeout(timer); }, [map]);
  return null;
}

function facilityIcon(color: string, selected: boolean) {
  const size = selected ? 18 : 12;
  const border = selected ? "3px solid white" : "2px solid rgba(255,255,255,0.8)";
  return divIcon({
    className: "",
    html: `<div style="width:${size}px; height:${size}px; background:${color}; border-radius:50%; border:${border}; box-shadow: 0 0 10px ${color}; transition: all 0.2s;"></div>`,
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
    popupAnchor: [0, -size/2],
  });
}
