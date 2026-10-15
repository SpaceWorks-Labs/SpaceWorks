import type { ReactNode } from "react";
import { FlowLayout } from "../../../components/layouts";

/** The compact request forms share one task frame; each form keeps its own validation and submit handler. */
export function RequestFlowDialog({ title, open, pending, onClose, formId, submitLabel, canSubmit = true, danger, children }: {
  title: string; open: boolean; pending: boolean; onClose: () => void; formId: string;
  submitLabel: string; canSubmit?: boolean; danger?: boolean; children: ReactNode;
}) {
  return <FlowLayout presentation="dialog" open={open} title={title} compact
    state={{ status: "ready" }} steps={[{ key: "confirm", label: "Review and confirm", state: "current" }]} current="confirm"
    onCancel={() => { if (!pending) onClose(); }} work={children}
    footer={{ next: { label: submitLabel, pending, pendingLabel: "Saving…", disabled: !canSubmit,
      disabledReason: !canSubmit ? "Accept at least one unit before continuing." : undefined, tone: danger ? "danger" : "default",
      onClick: () => (document.getElementById(formId) as HTMLFormElement | null)?.requestSubmit() } }} />;
}
