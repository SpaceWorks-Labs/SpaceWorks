import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../../components/ui/Card";
import { StatusResult } from "./PublicPrintRequestParts";
import type { PrintStatus } from "./publicApi";
import { OwnerCancel } from "../machine-service/OwnerCancel";
import { LogoLoader } from "../../components/LogoLoader";

type StatusProps = { submitted: boolean; tokenStatus?: PrintStatus; tokenStatusPending: boolean; tokenStatusError: Error | null; trackingHref?: string; onRetry?: () => void;
  /** With a token, the signed-in owner (only) gets a Cancel control for a live job. */
  publicToken?: string; makerspaceSlug?: string };
export function PrintStatusPanel({ submitted, tokenStatus, tokenStatusPending, tokenStatusError, trackingHref, onRetry, publicToken, makerspaceSlug = "" }: StatusProps) {
  const [copyState, setCopyState] = useState("");
  async function copyLink() {
    try { await navigator.clipboard.writeText(trackingHref!); setCopyState("Tracking link copied. Keep it private."); }
    catch { setCopyState("Couldn't copy the link. You can copy it from your browser's address bar."); }
  }
  return <div className="grid gap-4">
    {submitted ? <p className="text-sm" role="status">{t`Request submitted. This browser keeps its private token; do not share the link.`}</p> : null}
    <StatusResult error={tokenStatusError} isPending={tokenStatusPending} status={tokenStatus} onRetry={onRetry} />
    {publicToken && tokenStatus ? <OwnerCancel token={publicToken} title={tokenStatus.title} makerspaceSlug={makerspaceSlug}
      extraKeys={[["public-printer-status", publicToken]]} /> : null}
    {trackingHref ? <button className="desk-button w-full" type="button" onClick={() => { void copyLink(); }}>{t`Copy tracking link`}</button> : null}
    {copyState ? <p role="status" className="text-sm text-muted">{copyState}</p> : null}
  </div>;
}
export function PrintAccessLoadingPanel() { return <section className="mx-auto max-w-screen-sm px-5 py-6"><Card><LogoLoader label={t`Loading printer service...`} size={48} className="min-h-16 py-3" /></Card></section>; }
export function PrintAccessErrorPanel() { return <section className="mx-auto max-w-screen-sm px-5 py-6"><Card><p className="text-sm text-danger">{t`Could not load printer service. Try again in a moment.`}</p></Card></section>; }
export function PrintUnavailablePanel({ catalogPath, tokenStatus, tokenStatusPending, tokenStatusError }: { catalogPath: string; tokenStatus?: PrintStatus; tokenStatusPending: boolean; tokenStatusError: Error | null }) { return <section className="mx-auto max-w-screen-sm px-5 py-6"><Card className="border-brand"><p className="eyebrow text-brand-ink">{t`3D printing`}</p><h2 className="title-panel mt-2">{t`Printer service is not currently available.`}</h2>{tokenStatus || tokenStatusPending || tokenStatusError ? <div className="mt-4"><StatusResult error={tokenStatusError} isPending={tokenStatusPending} status={tokenStatus} /></div> : null}<Link className="desk-button mt-4" to={catalogPath}>{t`Back to inventory`}</Link></Card></section>; }
