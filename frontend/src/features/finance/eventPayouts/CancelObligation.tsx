import { useState } from "react";
import { usePayoutCommand } from "./api";
import type { FinanceScope, Payout } from "./types";

export function CancelObligation({ scope, payout, poolVersion }: { scope: FinanceScope; payout: Payout; poolVersion?: number }) {
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const mutation = usePayoutCommand(scope, payout.id, "cancel");
  const eligible = payout.state === "open" && payout.effective_paid_minor === 0 &&
    (payout.coordination_state === "detached" || poolVersion !== undefined);
  return <section className="grid gap-3 rounded-2xl border border-line p-5" aria-label="Cancel unpaid obligation">
    <h2 className="font-semibold">Cancel unpaid obligation</h2><p>This closes the liability and preserves its decision and receipt history. Any retention hold remains in effect.</p>
    <label className="grid gap-1">Reason code<input className="desk-input" value={reason} onChange={event => setReason(event.target.value)} /></label>
    <label className="grid gap-1">Finance explanation<textarea className="desk-input" maxLength={5000} value={note} onChange={event => setNote(event.target.value)} /></label>
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm this unpaid obligation should be cancelled.</label>
    <button className="desk-button-danger-outline min-h-11" type="button" disabled={!eligible || !confirmed || !note.trim() || !/^[a-z][a-z0-9_]{0,63}$/.test(reason) || mutation.isPending}
      onClick={() => mutation.mutate({ expected_version: payout.version, expected_revision_sequence: payout.current_revision_sequence,
        expected_pool_version: payout.coordination_state === "attached" ? poolVersion : null, reason_code: reason, note })}>Cancel unpaid obligation</button>
    {!eligible ? <p className="text-sm text-muted">Cancellation requires an unpaid open obligation and its current budget version when attached.</p> : null}
    {mutation.error ? <p role="alert">Cancellation failed. Reload current versions and confirm your recent finance authentication.</p> : null}
    {mutation.isSuccess ? <p role="status">The unpaid obligation was cancelled.</p> : null}
  </section>;
}
