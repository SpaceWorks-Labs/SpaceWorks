import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { Field } from "../../../components/ui";
import { ActionDialog } from "../platformSpaces/ActionDialog";

type Props = { title: string; message: ReactNode; confirmLabel: string; expected: string; what: string;
  pending: boolean; error: unknown; onConfirm: (typed: string) => void; onCancel: () => void };

/** A destructive or hard-to-undo action: the exact `expected` text must be typed before it runs (then the server asks for a fresh sign-in). */
export function TypedConfirmDialog({ title, message, confirmLabel, expected, what, pending, error, onConfirm, onCancel }: Props) {
  const [typed, setTyped] = useState("");
  return <ActionDialog title={title} tone="danger" confirmLabel={confirmLabel} pending={pending} error={error}
    canSubmit={typed.trim() === expected} onCancel={onCancel} message={message} onSubmit={() => onConfirm(typed.trim())}>
    <Field label={t`Type ${expected} to confirm`} hint={t`The ${what}, exactly.`}>
      <input className="desk-input" autoComplete="off" autoCapitalize="none" spellCheck={false} value={typed}
        onChange={event => setTyped(event.target.value)} />
    </Field>
  </ActionDialog>;
}
