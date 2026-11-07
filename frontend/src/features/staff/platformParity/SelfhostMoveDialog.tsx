import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "../platformSpaces/ActionDialog";
import { useMoveAction, type MoveAction, type SelfhostMove } from "./selfhostMovesApi";

type Copy = { title: string; confirm: string; done: string; danger?: boolean; message: (space: string) => string };
const COPY: Record<MoveAction, Copy> = {
  approve: { title: t`Approve this move`, confirm: t`Approve move`, done: t`Move approved.`,
    message: space => `You can then export ${space} for its new server. Nothing leaves the platform until you export it.` },
  reject: { title: t`Decline this move`, confirm: t`Decline move`, done: t`Move declined.`, danger: true,
    message: space => `The request from ${space} is closed and the space stays on this platform.` },
  export: { title: t`Export this space`, confirm: t`Start export`, done: t`Export started.`,
    message: space => `The data of ${space} is packed and encrypted to the key below. Only the server holding the matching private key can open it.` },
  discard: { title: t`Delete the export file`, confirm: t`Delete file`, done: t`Export file deleted.`, danger: true,
    message: space => `The encrypted export of ${space} is deleted from storage and can no longer be downloaded.` },
};
const NOTE_MAX = 500;
const AGE_KEY = /^age1\S{20,}$/i;

/** Approve, decline, export or delete the file of one move; each goes through a confirm dialog. */
export function SelfhostMoveDialog({ move, action, onClose }: { move: SelfhostMove; action: MoveAction; onClose: () => void }) {
  const copy = COPY[action];
  const mutation = useMoveAction(move.id, action);
  const [note, setNote] = useState("");
  const [recipient, setRecipient] = useState("");
  const key = recipient.trim();
  const keyError = key && !AGE_KEY.test(key) ? "This is not an age public key. It starts with age1." : undefined;
  const body: Record<string, string> = action === "export" ? { recipient: key } : action === "discard" ? {} : { note: note.trim() };
  return <ActionDialog title={copy.title} confirmLabel={copy.confirm} tone={copy.danger ? "danger" : "default"}
    message={copy.message(move.makerspace_name)} pending={mutation.isPending} error={mutation.error} onCancel={onClose}
    canSubmit={action !== "export" || Boolean(key && !keyError)}
    onSubmit={() => mutation.mutate(body, { onSuccess: () => { toast(copy.done); onClose(); } })}>
    {action === "approve" || action === "reject" ? <Field label={t`Note (optional)`} hint={`${note.length}/${NOTE_MAX} characters.`}>
      <textarea className="desk-input min-h-20" value={note} maxLength={NOTE_MAX} onChange={event => setNote(event.target.value)} />
    </Field> : null}
    {action === "export" ? <Field label={t`Target server's age public key`} error={keyError}
      hint={t`Paste the public key of the server the space is moving to. Never paste this platform's own key.`}>
      <input className="desk-input font-mono" value={recipient} maxLength={200} spellCheck={false} autoComplete="off"
        placeholder={t`age1…`} onChange={event => setRecipient(event.target.value)} />
    </Field> : null}
  </ActionDialog>;
}
