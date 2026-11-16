import { t } from "@lingui/core/macro";
import { useState, type FormEvent, type ReactNode } from "react";
import { Field, Modal } from "../../../components/ui";
import { authErrorMessage } from "../../../lib/api/authErrorCopy";
import { StructuredApiError } from "../../../lib/api/errors";
import { BoxArt } from "../../../components/BoxSpinner";

export type ReasonSpec = { label: string; min: number; max: number; hint?: string };

type Props = {
  title: string;
  message: ReactNode;
  confirmLabel: string;
  tone?: "danger" | "default";
  /** When set, the dialog asks for a reason and hands it to `onSubmit`. */
  reason?: ReasonSpec;
  pending: boolean;
  error: unknown;
  /** Extra fields; their values are the caller's state. `canSubmit` gates the confirm button. */
  children?: ReactNode;
  canSubmit?: boolean;
  onSubmit: (reason: string) => void;
  onCancel: () => void;
};

/** The text a failed platform control shows: auth codes in plain words, field errors joined. */
export function actionErrorText(error: unknown) {
  if (!error) return "";
  if (error instanceof StructuredApiError && error.status === 400 && !error.detail) {
    const parts = Object.entries(error.body).filter(([key]) => key !== "code").flatMap(([, value]) => Array.isArray(value) ? value : [value]);
    const text = parts.filter((part): part is string => typeof part === "string").join(" ");
    if (text) return text;
  }
  return authErrorMessage(error, "That didn't work. Try again.");
}

/** One confirm dialog for every lifecycle control; a reason is required where the contract needs one. */
export function ActionDialog({ title, message, confirmLabel, tone = "default", reason, pending, error, children, canSubmit = true, onSubmit, onCancel }: Props) {
  const [text, setText] = useState("");
  const trimmed = text.trim();
  const reasonOk = !reason || (trimmed.length >= reason.min && trimmed.length <= reason.max);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!pending && reasonOk && canSubmit) onSubmit(trimmed);
  };
  const formId = `platform-action-${title.replace(/\W+/g, "-").toLowerCase()}`;
  const errorText = actionErrorText(error);
  return <Modal open title={title} onClose={onCancel} footer={<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
    <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={onCancel}>{t`Cancel`}</button>
    <button type="submit" form={formId} className={`${tone === "danger" ? "desk-button-danger" : "desk-button-primary"} w-full sm:w-auto`}
      disabled={pending || !reasonOk || !canSubmit}>{pending ? <><BoxArt size={16} mono />{t`Working…`}</> : confirmLabel}</button>
  </div>}>
    <form id={formId} className="grid gap-4" onSubmit={submit} noValidate>
      <div className="text-sm text-muted">{message}</div>
      {children}
      {reason ? <Field label={reason.label} hint={reason.hint ?? `${trimmed.length}/${reason.max} characters · at least ${reason.min}.`}>
        <textarea className="desk-input min-h-24" value={text} maxLength={reason.max} onChange={(event) => setText(event.target.value)} />
      </Field> : null}
      {errorText ? <p role="alert" className="rounded-control border border-danger-line bg-panel px-3 py-2 text-sm text-danger">{errorText}</p> : null}
    </form>
  </Modal>;
}
