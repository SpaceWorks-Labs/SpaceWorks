import { useState } from "react";
import { Field } from "../../components/ui/Field";
import { StructuredApiError } from "../../lib/api/errors";
import { AccountDeletionReauthentication } from "./AccountDeletionReauthentication";
import { AccountDeletionBlockers } from "./AccountDeletionBlockers";
import { useDeleteAccount, useDeletionPreview, type DeletionBlocker, type DeletionResult } from "./accountDeletionApi";

export function AccountDeletionReceipt({ result }: { result: DeletionResult }) {
  return <section aria-labelledby="deletion-result-heading" className="grid gap-3">
    <h2 id="deletion-result-heading" className="title-panel">Account deletion requested</h2>
    <p role="status">Your account is inactive and you have been signed out on all devices. Identity removal is scheduled from {new Date(result.purge_after).toLocaleDateString()}.</p>
    <p>Accountability and financial records remain as described in the deletion notice. A makerspace migration or storage outage can delay identity removal.</p>
  </section>;
}

export function MemberAccountDeletion({ slug, onDeleted }: { slug: string; onDeleted: (result: DeletionResult) => void }) {
  const [confirmation, setConfirmation] = useState("");
  const preview = useDeletionPreview();
  const deletion = useDeleteAccount(onDeleted);
  const refusal = deletion.error instanceof StructuredApiError ? deletion.error.body.blockers as DeletionBlocker[] | undefined : undefined;
  const blockers = refusal || preview.data?.blockers || [];
  const ready = preview.data?.deletable && !blockers.length;
  const needsReauth = Boolean(preview.data?.reauth.required);
  return <section aria-labelledby="account-deletion-heading" className="grid min-w-0 gap-4">
    <h3 id="account-deletion-heading" className="title-section">Delete account</h3>
    <p>This deletes your account across every makerspace. Sign-in ends immediately. Identity copies are archived before removal (90 days by default). Eligible accounts can be restored only before the purge deadline and before identity removal begins.</p>
    <details className="rounded-xl border border-line p-3"><summary className="min-h-11 cursor-pointer text-ink">Records retained after deletion</summary>
      <p className="mt-2 text-sm text-muted">Audit logs; payments, refunds, manual settlements and historical payer labels; accountability and return events; evidence metadata (photos follow evidence retention); machine usage, attendance certificates and feedback; staff notification emails, delivery-log text and staff actor snapshots on other members’ records. Notification logs and backups follow their existing retention periods.</p>
    </details>
    <p className="text-sm text-muted">If you used Apple, we will attempt to revoke its authorization. If no token is available or revocation fails, remove Space Works under Sign in with Apple in your Apple Account settings.</p>
    <a className="text-brand-ink underline" href="https://account.apple.com/account/manage">Manage Sign in with Apple</a>
    {preview.isLoading ? <p role="status">Checking account obligations…</p> : null}
    {preview.error ? <div><p role="alert" className="text-danger">{preview.error.message}</p><button type="button" className="desk-button" onClick={() => void preview.refetch()}>Retry deletion check</button></div> : null}
    {blockers.length ? <><p role="status">Resolve these items before deleting your account.</p><AccountDeletionBlockers blockers={blockers} slug={slug} /></> : null}
    {ready && preview.data ? <>
      <p role="status" className="text-sm text-muted">{preview.data.restorable ? "Recovery during the archive window: " : "This account cannot be restored: "}{preview.data.restore_reason}</p>
      {needsReauth ? <AccountDeletionReauthentication methods={preview.data.reauth.methods} onVerified={() => { void preview.refetch(); }} /> : <p role="status">Your recent sign-in is confirmed.</p>}
      <form className="grid gap-3" onSubmit={event => { event.preventDefault(); if (confirmation === "DELETE" && !needsReauth) deletion.mutate(); }}>
        <Field label="Type DELETE to confirm" hint="This affects your whole account and all makerspace memberships."><input className="desk-input" value={confirmation} autoComplete="off" spellCheck={false} onChange={event => setConfirmation(event.target.value)} /></Field>
        <button className="desk-button-danger" disabled={confirmation !== "DELETE" || needsReauth || deletion.isPending}>{deletion.isPending ? "Deleting account…" : "Delete account permanently"}</button>
      </form>
    </> : null}
    {deletion.error ? <p role="alert" className="text-danger">{deletion.error.message}</p> : null}
    {preview.data ? <button type="button" className="desk-button" disabled={preview.isFetching || deletion.isPending} onClick={() => { void preview.refetch(); }}>Refresh deletion check</button> : null}
  </section>;
}
