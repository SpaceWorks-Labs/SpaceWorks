import { useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { StatusResult } from "./PublicPrintRequestParts";
import type { PrintStatus } from "./publicApi";

type StatusProps = { submitted: boolean; tokenStatus?: PrintStatus; tokenStatusPending: boolean; tokenStatusError: Error | null; trackingHref?: string; onRetry?: () => void };
export function PrintStatusPanel({ submitted, tokenStatus, tokenStatusPending, tokenStatusError, trackingHref, onRetry }: StatusProps) {
  const [copyState, setCopyState] = useState("");
  async function copyLink() {
    try { await navigator.clipboard.writeText(trackingHref!); setCopyState("Tracking link copied. Keep it private."); }
    catch { setCopyState("Couldn't copy the link. You can copy it from your browser's address bar."); }
  }
  return <div className="grid gap-4">
    {submitted ? <p className="text-sm" role="status">Request submitted. This browser keeps its private token; do not share the link.</p> : null}
    <StatusResult error={tokenStatusError} isPending={tokenStatusPending} status={tokenStatus} onRetry={onRetry} />
    {trackingHref ? <button className="desk-button w-full" type="button" onClick={() => { void copyLink(); }}>Copy tracking link</button> : null}
    {copyState ? <p role="status" className="text-sm text-muted">{copyState}</p> : null}
  </div>;
}
export function PrintAccessLoadingPanel() { return <section className="mx-auto max-w-screen-sm px-5 py-6"><Card><p className="text-sm text-muted">Loading printer service...</p></Card></section>; }
export function PrintAccessErrorPanel() { return <section className="mx-auto max-w-screen-sm px-5 py-6"><Card><p className="text-sm text-danger">Could not load printer service. Try again in a moment.</p></Card></section>; }
export function PrintUnavailablePanel({ catalogPath, tokenStatus, tokenStatusPending, tokenStatusError }: { catalogPath: string; tokenStatus?: PrintStatus; tokenStatusPending: boolean; tokenStatusError: Error | null }) { return <section className="mx-auto max-w-screen-sm px-5 py-6"><Card className="border-brand"><p className="eyebrow text-brand-ink">3D printing</p><h2 className="title-panel mt-2">Printer service is not currently available.</h2>{tokenStatus || tokenStatusPending || tokenStatusError ? <div className="mt-4"><StatusResult error={tokenStatusError} isPending={tokenStatusPending} status={tokenStatus} /></div> : null}<Link className="desk-button mt-4" to={catalogPath}>Back to inventory</Link></Card></section>; }
