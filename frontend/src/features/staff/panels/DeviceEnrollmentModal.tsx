import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Callout, RelativeTime } from "../../../components/ui";
import { FlowLayout } from "../../../components/layouts";
import type { EnrollmentGrant } from "../devicesApi";

export function DeviceEnrollmentModal({ grant, onClose }: { grant: EnrollmentGrant; onClose: () => void }) {
  const [copyState, setCopyState] = useState("");
  return <FlowLayout presentation="dialog" open title={t`One-time device enrollment`} state={{ status: "ready" }} steps={[]} current="token"
    onCancel={onClose} footer={{ next: { label: t`I’ve copied it`, onClick: onClose } }} work={<div className="grid gap-4">
    <Callout size="inline" tone="warn" lead="Copy this now." body={t`It won’t be shown again.`} />
    <p>{t`Copy this bearer token to the device now. Closing discards it; it cannot be read again.`}</p>
    <p className="text-sm text-muted">{t`Purpose: ${grant.purpose} · Expires `}<RelativeTime date={grant.expires_at} /></p>
    <label>{t`Enrollment identifier`}<input className="desk-input block w-full" readOnly value={grant.enrollment_id} /></label>
    <label>{t`Enrollment token`}<textarea className="desk-input block min-h-32 w-full bg-ink text-panel tabular-nums slashed-zero tracking-wide" readOnly value={grant.token} /></label>
    <button className="desk-button mt-3" onClick={async () => {
      try { await navigator.clipboard.writeText(JSON.stringify(grant)); setCopyState("Enrollment copied. Clear your clipboard after use."); }
      catch { setCopyState("Copy unavailable. Select and copy the identifier and token manually."); }
    }}>{t`Copy enrollment`}</button>
    <p role="status">{copyState}</p>
  </div>} />;
}
