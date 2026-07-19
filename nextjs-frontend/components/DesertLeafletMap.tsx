"use client";
import { CircleMarker, MapContainer, Popup, TileLayer, ZoomControl } from "react-leaflet";
import { STATE_CENTROIDS } from "@/lib/india";
import { useTheme } from "./ThemeToggle";
export type TrustPin={name:string;lat:number;lon:number;score:number;verdict:string;flags:string[]};
export default function DesertLeafletMap({mode,deserts,covered,pinCounts,trustPins,spotlight}:{mode:string;deserts:string[];covered:string[];pinCounts:Record<string,number>;trustPins:TrustPin[];spotlight?:{pin:string;state:string}}){const theme=useTheme();
 const states=mode==="coverage"?[...deserts,...covered]:mode==="hotspot"?covered:[];
 const pressure=mode==="coverage"?deserts.flatMap((state)=>scatter(state,Math.min(28,Math.max(4,pinCounts[state]||4)))):[];
 const center=spotlight&&STATE_CENTROIDS[spotlight.state]?STATE_CENTROIDS[spotlight.state]:[22.9734,78.6569] as [number,number];
 return <MapContainer center={center} zoom={spotlight?7:5} zoomControl={false} scrollWheelZoom className="dm-leaflet"><TileLayer key={theme} attribution="&copy; OpenStreetMap contributors &copy; CARTO" url={`https://{s}.basemaps.cartocdn.com/${theme==="light"?"light_all":"dark_all"}/{z}/{x}/{y}{r}.png`}/><ZoomControl position="topleft"/>
 {pressure.map((p,i)=><CircleMarker key={`heat-${i}`} center={p} radius={9} pathOptions={{stroke:false,fillColor:"#ef4444",fillOpacity:.12}}/>)}
 {states.map(state=>{const pos=STATE_CENTROIDS[state];if(!pos)return null;const desert=deserts.includes(state);const count=pinCounts[state]||0;return <CircleMarker key={state} center={pos} radius={desert?Math.min(18,8+count/4):7} pathOptions={{color:desert?"#991b1b":"#047857",fillColor:desert?"#dc2626":"#10b981",fillOpacity:.78,weight:1.5}}><Popup><b>{state}</b><br/>{desert?"Coverage gap":"Specialty covered"}<br/>{count?`${count} desert PINs (estimated distribution)`:"State-centroid indicator"}</Popup></CircleMarker>})}
 {mode==="trust"&&trustPins.map((p,i)=><CircleMarker key={`${p.name}-${i}`} center={[p.lat,p.lon]} radius={9} pathOptions={{color:p.verdict==="VERIFIED"?"#047857":p.verdict==="SUSPICIOUS"?"#be123c":"#d97706",fillColor:p.verdict==="VERIFIED"?"#10b981":p.verdict==="SUSPICIOUS"?"#f43f5e":"#f59e0b",fillOpacity:.9,weight:2}}><Popup><b>{p.name}</b><br/>{p.verdict} · {Math.round(p.score*100)}%<br/>{p.flags.slice(0,2).join("; ")}</Popup></CircleMarker>)}
 {spotlight&&STATE_CENTROIDS[spotlight.state]&&<CircleMarker center={STATE_CENTROIDS[spotlight.state]} radius={20} pathOptions={{color:"#2563eb",fillColor:"#60a5fa",fillOpacity:.25,weight:3}}><Popup><b>PIN {spotlight.pin}</b><br/>{spotlight.state}</Popup></CircleMarker>}
 </MapContainer>}
function scatter(state:string,count:number):[number,number][]{const c=STATE_CENTROIDS[state];if(!c)return[];return Array.from({length:count},(_,i)=>{const a=(i*137.5)*Math.PI/180,r=.12+.035*Math.sqrt(i+1);return[c[0]+Math.sin(a)*r,c[1]+Math.cos(a)*r]})}
