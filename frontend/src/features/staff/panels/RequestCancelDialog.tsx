import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ErrorText, Field, Modal } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import type { HardwareRequest } from "./Queues";
import { invalidateRequestQueues } from "./QueuesInvalidation";

/** Staff cancel a pending or accepted request; the workflow releases any reservation it held. */
export function RequestCancelDialog({ row, makerspaceId, onClose }: { row: HardwareRequest; makerspaceId: number; onClose: () => void }) {
  const client = useQueryClient();
  const [reason, setReason] = useState("");
  const cancel = useMutation({
    mutationFn: () => staffRequest<{ id: number; status: string; closed_at: string | null }>(
      `/admin/makerspace/${makerspaceId}/requests/${row.id}/cancel`, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) }),
    onSuccess: () => {
      invalidateRequestQueues(client, makerspaceId, { inventory: true, ledger: false, needsFix: false });
      void client.invalidateQueries({ queryKey: ["dashboard", makerspaceId] });
      onClose();
    },
  });
  const who = row.requester_display || row.requester_username;
  return <Modal open onClose={() => { if (!cancel.isPending) onClose(); }} title={`Cancel request #${row.id}?`}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); cancel.mutate(); }}>
      <p className="text-sm text-muted">{who}'s request closes as Cancelled{row.status === "accepted" ? " and the items it held go back on the shelf" : ""}. This can't be undone.</p>
      <Field label="Reason (optional)" hint="Shown in the request history."><textarea className="desk-input min-h-20" maxLength={500} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      <ErrorText message={cancel.error?.message} />
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" disabled={cancel.isPending} onClick={onClose}>Keep request</button>
        <button type="submit" className="desk-button-danger" disabled={cancel.isPending}>{cancel.isPending ? "Cancelling…" : "Cancel request"}</button>
      </div>
    </form>
  </Modal>;
}
