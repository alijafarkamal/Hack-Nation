"use client";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export type ThemeMode="dark"|"light";
const EVENT="carecompass-theme-change";
export function getTheme():ThemeMode{return typeof document!=="undefined"&&document.documentElement.dataset.theme==="light"?"light":"dark"}
export function useTheme(){const[theme,setTheme]=useState<ThemeMode>("dark");useEffect(()=>{const sync=()=>setTheme(getTheme());sync();window.addEventListener(EVENT,sync);return()=>window.removeEventListener(EVENT,sync)},[]);return theme}
export default function ThemeToggle({className=""}:{className?:string}){const theme=useTheme();function toggle(){const next:ThemeMode=theme==="dark"?"light":"dark";document.documentElement.dataset.theme=next;localStorage.setItem("carecompass-theme",next);window.dispatchEvent(new Event(EVENT))}return <button type="button" className={`theme-toggle ${className}`} onClick={toggle} title={`Switch to ${theme==="dark"?"light":"dark"} mode`} aria-label={`Switch to ${theme==="dark"?"light":"dark"} mode`}>{theme==="dark"?<Sun/>:<Moon/>}</button>}
