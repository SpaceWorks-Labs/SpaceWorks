import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Copy } from "lucide-react";

import { Field, Modal } from "../../components/ui";
import { financeApi, financeError } from "./financeApi";

/** Create a pay link for an account-less charge staff raised; optionally email it once. */
export function PayLinkDialog({ makerspaceId, paymentId, label, onClose, createLink }: {
  makerspaceId: number; paymentId: number; label: string; onClose: () => void;
  /** Decision 242(b): an area's own queue creates the link through its owner-scoped route instead. */
  createLink?: (email: string) => Promise<{ url: string; expires_at: string; emailed: boolean }>;
}) {
  const [email, setEmail] = useState("");
  const [copied, setCopied] = useState(false);
  const create = useMutation({ mutationFn: () => createLink ? createLink(email) : financeApi.payLink(makerspaceId, paymentId, email) });
  return <Modal open onClose={onClose} title={t`Pay link`}>
    {create.data ? <div className="grid gap-3">
      <p className="text-sm">{t`Anyone with this link can pay `}<strong>{label}</strong> until {create.data.expires_at.slice(0, 10)}.
        It shows the amount, never who owes it. A new link replaces this one.</p>
      <p className="break-all rounded-md border border-line bg-panel p-2 code-text text-sm">{create.data.url}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" onClick={() => { void navigator.clipboard?.writeText(create.data!.url); setCopied(true); }}>
          <Copy aria-hidden="true" size={16} />{copied ? t`Copied` : t`Copy link`}</button>
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Done`}</button>
      </div>
      {create.data.emailed ? <p role="status" className="text-sm">{t`The link was emailed.`}</p> : null}
    </div> : <form className="grid gap-3" onSubmit={event => { event.preventDefault(); create.mutate(); }}>
      <p className="text-sm">{t`For a charge with no account behind it. The payer can pay online or tell you they paid.`}</p>
      <Field label={t`Email it to (optional)`} hint={t`Sent once; the address is not stored.`}><input type="email" className="desk-input"
        value={email} onChange={event => setEmail(event.target.value)} /></Field>
      {create.error ? <p role="alert" className="text-sm text-danger">{financeError(create.error)}</p> : null}
      <div className="flex justify-end gap-2"><button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button" disabled={create.isPending}>{t`Create link`}</button></div>
    </form>}
  </Modal>;
}
