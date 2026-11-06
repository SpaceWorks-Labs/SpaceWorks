import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "../platformSpaces/ActionDialog";
import { useQueueDecision, type QueueDecision, type QueueKind } from "./requestsApi";

const NOTE_MAX = 2000;

type Props = {
  kind: QueueKind; id: number; decision: QueueDecision;
  title: string; confirm: string; message: string; done: string; danger?: boolean;
  /** "optional" adds a note field; "required" asks for one before the confirm button works. */
  note?: "optional" | "required";
  onClose: () => void;
};

/** Approve, decline or reject one queued request, with an optional or required note. */
export function QueueDecisionDialog({ kind, id, decision, title, confirm, message, done, danger, note, onClose }: Props) {
  const mutation = useQueueDecision<unknown>(kind, id, decision);
  const [text, setText] = useState("");
  const finish = { onSuccess: () => { toast(done); onClose(); } };
  return <ActionDialog title={title} confirmLabel={confirm} message={message} tone={danger ? "danger" : "default"}
    pending={mutation.isPending} error={mutation.error} onCancel={onClose}
    reason={note === "required" ? { label: t`Note`, min: 1, max: NOTE_MAX } : undefined}
    onSubmit={reason => mutation.mutate(note === "required" ? { note: reason } : note === "optional" ? { note: text.trim() } : {}, finish)}>
    {note === "optional" ? <Field label={t`Note (optional)`} hint={`${text.length}/${NOTE_MAX} characters.`}>
      <textarea className="desk-input min-h-20" value={text} maxLength={NOTE_MAX} onChange={event => setText(event.target.value)} />
    </Field> : null}
  </ActionDialog>;
}
