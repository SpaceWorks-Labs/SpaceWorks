import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { AuthStepCard } from "./AuthStepCard";
import type { MfaCompleted } from "./mfaApi";

/** After enrolment: the one-time recovery codes, acknowledged before sign-in continues. */
export function MfaRecoveryCodesStep({ completed, onContinue, embedded, eyebrow, extra }: {
  completed: MfaCompleted; onContinue: () => void; embedded: boolean; eyebrow?: string; extra?: ReactNode;
}) {
  const [copyNotice, setCopyNotice] = useState("");
  const codes = completed.recovery_codes ?? [];
  async function copy() {
    try { await navigator.clipboard.writeText(codes.join("\n")); setCopyNotice(t`Copied. Store it somewhere secure.`); }
    catch { setCopyNotice(t`Couldn't copy. Select the text and copy it manually.`); }
  }
  return <AuthStepCard embedded={embedded} eyebrow={eyebrow} state={{ status: "ready" }}
    media={{ icon: "CheckCircle", tone: "success" }} title={t`Save your recovery codes`}
    body={t`Each code works once. Save these somewhere secure; they will not be shown again.`}
    primary={{ label: t`I saved my codes. Continue`, onClick: onContinue }} footer={extra}
    content={<div className="grid gap-4">
      <ul className="grid grid-cols-2 gap-2">{codes.map(value => <li className="min-w-0 break-all rounded-control border border-line bg-surface p-3 code-text text-sm" key={value}>{value}</li>)}</ul>
      <button type="button" className="desk-button" onClick={() => void copy()}>{t`Copy all codes`}</button>
      <p role="status" className="text-sm text-muted empty:hidden">{copyNotice}</p>
      <a className="desk-button" download="space-works-recovery-codes.txt" href={`data:text/plain;charset=utf-8,${encodeURIComponent(codes.join("\n"))}`}>{t`Download codes`}</a>
    </div>} />;
}
