import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Field, StatusPill } from "../../../components/ui";
import { formatDateTime } from "../../../lib/format";
import { guestErrorText, guestStaffApi, type ScanResult } from "../api";
import { entitlementSummary, passKindLabel, scanReasonLabel } from "../labels";

/** A guest-pass QR carries `gp1.<id>.<signature>` (decision 223 L4). */
export const isGuestPassToken = (value: string) => /^gp1\.\d+\.[A-Za-z0-9_-]+$/.test(value.trim());

/** What one desk scan says about a pass. Reads only: scanning never changes the pass. */
export function GuestPassScanResult({ result }: { result: ScanResult }) {
  return <div role="status" className={`grid gap-1 rounded-control border p-3 text-sm ${result.valid ? "border-success" : "border-danger-line"}`}>
    <p className="flex flex-wrap items-center gap-2 font-semibold text-ink">
      <StatusPill tone={result.valid ? "success" : "danger"} label={result.valid ? t`Valid pass` : t`Not valid`} />
      {result.holder_name || t`Unknown guest`}{result.kind ? <span className="font-normal text-muted"> · {passKindLabel(result.kind)}</span> : null}
    </p>
    {result.valid
      ? <p className="text-muted">{result.valid_until ? t`Valid until ${formatDateTime(result.valid_until)}.` : null} {entitlementSummary(result.entitlements)}</p>
      : <p className="text-danger">{scanReasonLabel(result.reason)}</p>}
  </div>;
}

/** Desk check of a guest pass: type or paste the code from the guest's phone or wallet pass. */
export function GuestPassScan({ makerspaceId }: { makerspaceId: number }) {
  const [token, setToken] = useState("");
  const scan = useMutation({ mutationFn: (value: string) => guestStaffApi.scan(makerspaceId, value.trim()) });
  return <section aria-label={t`Check a guest pass`} className="grid gap-2 rounded-2xl border border-line p-4">
    <h3 className="title-section">{t`Check a guest pass`}</h3>
    <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); if (token.trim()) scan.mutate(token); }}>
      <Field label={t`Pass code`} hint={t`Scan the guest's QR in the Scanner tab, or paste the code here.`} className="min-w-0 flex-1 basis-56">
        <input className="desk-input" autoComplete="off" value={token} onChange={(event) => { setToken(event.target.value); scan.reset(); }} />
      </Field>
      <button className="desk-button min-h-11" type="submit" disabled={!token.trim() || scan.isPending}>{scan.isPending ? t`Checking…` : t`Check pass`}</button>
    </form>
    {scan.data ? <GuestPassScanResult result={scan.data} /> : null}
    {scan.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(scan.error)}</p> : null}
  </section>;
}
