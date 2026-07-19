"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect } from "react";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error("CareCompass page error", error); }, [error]);
  return <main className="fatal-error">
    <div><AlertTriangle/><span>CareCompass recovery</span></div>
    <h1>The dashboard could not finish loading.</h1>
    <p>{error.message || "An unexpected frontend error occurred."}</p>
    {error.digest && <small>Reference: {error.digest}</small>}
    <button onClick={reset}><RefreshCw/>Try again</button>
  </main>;
}
