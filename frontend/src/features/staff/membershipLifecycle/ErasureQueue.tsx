import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, ListRow, Modal, StatusPill } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { lifecycleApi, lifecycleKeys, type ErasureRow } from "../membershipLifecycleApi";
import { Panel } from "../panels/shared";

const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : "That did not work.");

/** X29: members asking this space to erase their membership data. Money and the audit log stay. */
export function ErasureQueue({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const rows = useQuery({ queryKey: lifecycleKeys.erasure(makerspaceId), queryFn: () => lifecycleApi.erasure(makerspaceId) });
  const [deciding, setDeciding] = useState<{ row: ErasureRow; decision: "approve" | "reject" } | null>(null);
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: (target: { row: ErasureRow; decision: "approve" | "reject" }) =>
      lifecycleApi.decideErasure(target.row.id, target.decision, note.trim()),
    onSuccess: () => { setDeciding(null); setNote(""); void client.invalidateQueries({ queryKey: lifecycleKeys.erasure(makerspaceId) }); },
  });
  const rejecting = deciding?.decision === "reject";
  return <Panel title="Erasure requests">
    <p className="mb-3 text-sm text-muted">Approving anonymises what this space holds about the membership and ends it. Payment records and the audit log are kept; the account is never deleted.</p>
    {rows.isSuccess && !rows.data.length ? <EmptyState message="No erasure requests." /> : null}
    {rows.data?.map((row) => <ListRow key={row.id} title={row.member_name || row.member_email} identity={{ kind: "icon", icon: "ShieldAlert", tone: "warn" }}
      meta={<>{new Date(row.created_at).toLocaleDateString()}{row.member_note ? ` · “${row.member_note}”` : ""}</>}
      right={row.status === "requested" ? <div className="flex flex-wrap gap-2">
        <button className="desk-button" type="button" onClick={() => setDeciding({ row, decision: "reject" })}>Reject</button>
        <button className="desk-button-primary" type="button" onClick={() => setDeciding({ row, decision: "approve" })}>Approve</button>
      </div> : <StatusPill tone={row.status === "approved" ? "success" : "neutral"} label={row.status} />} />)}
    <Modal open={Boolean(deciding)} onClose={() => { if (!decide.isPending) setDeciding(null); }}
      title={rejecting ? "Reject erasure request" : "Approve erasure request"}
      footer={<div className="flex flex-wrap justify-end gap-2">
        <button className="desk-button" type="button" disabled={decide.isPending} onClick={() => setDeciding(null)}>Cancel</button>
        <button className="desk-button-primary" type="button"
          disabled={decide.isPending || (rejecting && !note.trim())} onClick={() => deciding && decide.mutate(deciding)}>
          {decide.isPending ? "Saving…" : rejecting ? "Reject" : "Approve and erase"}</button>
      </div>}>
      <div className="grid gap-3">
        {!rejecting ? <p className="text-sm text-ink">The membership ends now. Their record, titles, profile and application answers here are erased.</p> : null}
        <Field label={rejecting ? "Note for the member (required)" : "Note for the member (optional)"}>
          <textarea className="desk-input min-h-20" maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
        </Field>
        {decide.error ? <p role="alert" className="text-sm text-danger">{errorText(decide.error)}</p> : null}
      </div>
    </Modal>
  </Panel>;
}
