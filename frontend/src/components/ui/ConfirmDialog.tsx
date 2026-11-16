import { t } from "@lingui/core/macro";
import { Modal } from "./Modal";

export type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "default";
  onConfirm: () => void;
  onCancel: () => void;
  pending?: boolean;
  safePrimary?: boolean;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = t`Confirm`,
  cancelLabel = t`Cancel`,
  tone = "default",
  onConfirm,
  onCancel,
  pending = false,
  safePrimary = false,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      footer={(
        <div className="desk-actions flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
          <button className={`${safePrimary ? "desk-button-primary" : "desk-button"} w-full sm:w-auto`} type="button" disabled={pending} onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            className={`${safePrimary ? "desk-button-danger-outline" : tone === "danger" ? "desk-button-danger" : "desk-button-primary"} w-full sm:w-auto`}
            type="button"
            disabled={pending}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      )}
    >
      <p className={tone === "danger" ? "break-words rounded-control border border-danger-line bg-panel p-4 text-sm text-danger" : "break-words text-sm text-muted"}>{message}</p>
    </Modal>
  );
}
