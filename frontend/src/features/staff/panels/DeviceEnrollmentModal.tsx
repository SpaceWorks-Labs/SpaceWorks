import { useState } from "react";
import { Callout, RelativeTime } from "../../../components/ui";
import { FlowLayout } from "../../../components/layouts";
import type { EnrollmentGrant } from "../devicesApi";

export function DeviceEnrollmentModal({ grant, onClose }: { grant: EnrollmentGrant; onClose: () => void }) {
  const [copyState, setCopyState] = useState("");
  return <FlowLayout presentation="dialog" open title="One-time device enrollment" state={{ status: "ready" }} steps={[]} current="token"
    onCancel={onClose} footer={{ next: { label: "I’ve copied it", onClick: onClose } }} work={<div className="grid gap-4">
    <Callout size="inline" tone="warn" lead="Copy this now." body="It won’t be shown again." />
    <p>Copy this bearer token to the device now. Closing discards it; it cannot be read again.</p>
    <p className="text-sm text-muted">Purpose: {grant.purpose} · Expires <RelativeTime date={grant.expires_at} /></p>
    <label>Enrollment identifier<input className="desk-input block w-full" readOnly value={grant.enrollment_id} /></label>
    <label>Enrollment token<textarea className="desk-input block min-h-32 w-full bg-ink text-panel tabular-nums slashed-zero tracking-wide" readOnly value={grant.token} /></label>
    <button className="desk-button mt-3" onClick={async () => {
      try { await navigator.clipboard.writeText(JSON.stringify(grant)); setCopyState("Enrollment copied. Clear your clipboard after use."); }
      catch { setCopyState("Copy unavailable. Select and copy the identifier and token manually."); }
    }}>Copy enrollment</button>
    <p role="status">{copyState}</p>
  </div>} />;
}
