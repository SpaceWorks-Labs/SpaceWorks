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
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
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
        <div className="desk-actions flex flex-wrap justify-end gap-2">
          <button className={safePrimary ? "desk-button-primary" : "desk-button"} type="button" disabled={pending} onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            className={safePrimary ? "desk-button-danger-outline" : tone === "danger" ? "desk-button-danger" : "desk-button-primary"}
            type="button"
            disabled={pending}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      )}
    >
      <p className={tone === "danger" ? "rounded-control border border-danger-line bg-panel p-4 text-sm text-danger" : "text-sm text-muted"}>{message}</p>
    </Modal>
  );
}
