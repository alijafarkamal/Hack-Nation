"use client";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <html lang="en"><body><main style={{minHeight:"100vh",display:"grid",placeItems:"center",background:"#030d22",color:"#eef3ff",fontFamily:"sans-serif"}}><section style={{maxWidth:520,padding:32,textAlign:"center"}}><h1>CareCompass encountered an unexpected error.</h1><p style={{color:"#94a3b8"}}>{error.message || "Please reload the application."}</p>{error.digest&&<small>Reference: {error.digest}</small>}<br/><button onClick={reset} style={{marginTop:20,padding:"10px 18px",border:0,borderRadius:8,color:"white",background:"#7c3aed"}}>Reload dashboard</button></section></main></body></html>;
}
