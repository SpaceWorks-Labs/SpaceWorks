import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Callout } from "../../../components/ui";
import { formatDateTime } from "../../../lib/format";

/**
 * A webhook room's signing secret, shown exactly once (parity A10): after the server generates it on create,
 * and after a rotation. It is never readable again, so the warning comes first and Done is the only way out.
 */
export function SigningSecretReveal({ secret, previousValidUntil, onDone }: {
  secret: string; previousValidUntil?: string | null; onDone: () => void;
}) {
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");
  const copy = () => navigator.clipboard?.writeText(secret).then(() => setCopied("done"), () => setCopied("failed")) ?? setCopied("failed");
  return <section aria-label={t`New signing secret`} className="grid gap-3 rounded-control border border-line bg-warn-soft p-3">
    <Callout size="inline" tone="warn" lead={t`Copy this signing secret now.`}
      body={t`It is shown once and cannot be read again. Your endpoint uses it to check the X-SpaceWorks-Signature header.`} />
    <p className="break-all rounded-control border border-line bg-bg p-2 code-text text-xs text-ink" data-testid="signing-secret">{secret}</p>
    {previousValidUntil ? <p className="text-sm text-ink">{t`The previous secret keeps working until ${formatDateTime(previousValidUntil)}, so you can switch your endpoint over.`}</p> : null}
    <div className="flex flex-wrap items-center gap-2">
      <button className="desk-button" type="button" onClick={() => { void copy(); }}>{t`Copy secret`}</button>
      <button className="desk-button-primary" type="button" onClick={onDone}>{t`I've saved it`}</button>
      <span role="status" className="text-sm text-muted">{copied === "done" ? t`Copied.` : copied === "failed" ? t`Copy failed. Select the text and copy it by hand.` : ""}</span>
    </div>
  </section>;
}
