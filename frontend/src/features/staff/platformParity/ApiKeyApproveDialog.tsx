import { useState } from "react";
import { Modal } from "../../../components/ui";
import { ActionDialog } from "../platformSpaces/ActionDialog";
import { useQueueDecision, type ApiKeyRequest, type IssuedClient } from "./requestsApi";

/**
 * Approving issues an API client; its secret comes back once, in this mutation's result, and is
 * shown here and nowhere else. Closing the dialog resets the mutation, so the secret is gone.
 */
export function ApiKeyApproveDialog({ row, onClose }: { row: ApiKeyRequest; onClose: () => void }) {
  const approve = useQueueDecision<IssuedClient>("api-key-requests", row.id, "approve");
  const [copied, setCopied] = useState("");
  const close = () => { approve.reset(); onClose(); };
  const issued = approve.data;
  if (!issued) {
    return <ActionDialog title="Approve this API key" confirmLabel="Approve and issue key" pending={approve.isPending} error={approve.error}
      onCancel={close} onSubmit={() => approve.mutate({})}
      message={`${row.makerspace_name} gets an API client named "${row.label}"${row.allowed_origins.length ? `, limited to ${row.allowed_origins.join(", ")}` : ""}. Its secret is shown once, next.`} />;
  }
  const copy = () => {
    void Promise.resolve().then(() => navigator.clipboard.writeText(issued.client_secret))
      .then(() => setCopied("Secret copied.")).catch(() => setCopied("Couldn't copy. Select the secret to copy it."));
  };
  return <Modal open title="API key issued" onClose={close} footer={<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
    <button type="button" className="desk-button w-full sm:w-auto" onClick={copy}>Copy secret</button>
    <button type="button" className="desk-button-primary w-full sm:w-auto" onClick={close}>Done</button>
  </div>}>
    <div className="grid gap-3 text-sm">
      <p className="font-semibold text-ink">Copy it now; it cannot be shown again.</p>
      <p className="text-muted">Client ID</p>
      <p className="code-text break-all rounded-control border border-line bg-bg p-2 text-xs text-ink">{issued.client_id}</p>
      <p className="text-muted">Client secret</p>
      <p className="code-text break-all rounded-control border border-line bg-bg p-2 text-xs text-ink">{issued.client_secret}</p>
      {copied ? <p role="status" className="text-muted">{copied}</p> : null}
    </div>
  </Modal>;
}
