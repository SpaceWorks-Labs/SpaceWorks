import { t } from "@lingui/core/macro";
import { Modal } from "../../../components/ui";
import type { Confirm } from "./modulePlans";

export function ModuleConfirm({ confirm, pending, onConfirm, onCancel }: { confirm: Confirm | null; pending: boolean; onConfirm: () => void; onCancel: () => void }) {
  return <Modal open={confirm !== null} onClose={onCancel} title={confirm?.title ?? ""}
    footer={<div className="desk-actions flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
      <button type="button" className="desk-button w-full sm:w-auto" disabled={pending} onClick={onCancel}>{t`Cancel`}</button>
      <button type="button" className="desk-button-primary w-full sm:w-auto" disabled={pending} onClick={onConfirm}>{confirm?.confirmLabel ?? t`Confirm`}</button>
    </div>}>
    <p className="break-words text-sm text-muted">{confirm?.message}</p>
    {confirm?.lines.length ? <ul className="mt-3 grid max-h-64 gap-1 overflow-auto text-sm text-ink">
      {confirm.lines.map(line => <li key={line} className="break-words border-t border-line pt-1 first:border-0 first:pt-0">{line}</li>)}</ul> : null}
    <p className="mt-3 text-sm text-muted">{t`You can undo this right after.`}</p>
  </Modal>;
}
