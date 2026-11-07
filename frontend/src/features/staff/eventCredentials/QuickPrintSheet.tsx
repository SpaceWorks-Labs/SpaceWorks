import { t } from "@lingui/core/macro";
import { Modal } from "../../../components/ui";

export function QuickPrintSheet({ open, canPrint, name, pending, onPrint, onSkip, onEdit, printDisabled = false, error }: {
  open: boolean; canPrint: boolean; name: string; pending: boolean;
  onPrint: () => void; onSkip: () => void; onEdit: () => void; printDisabled?: boolean; error?: string;
}) {
  return <Modal open={open && canPrint} onClose={onSkip} title={t`Print an event ID card?`}
    footer={<div className="flex flex-wrap gap-2"><button className="desk-button" type="button" onClick={onSkip}>{t`Skip`}</button>
      <button className="desk-button" type="button" onClick={onEdit}>{t`Edit design`}</button>
      <button className="desk-button-primary" type="button" autoFocus disabled={pending || printDisabled} onClick={onPrint}>{t`Print (Enter)`}</button></div>}>
    <div onKeyDown={(event) => { if (event.key === "Enter" && !pending && !printDisabled && event.target === event.currentTarget) { event.preventDefault(); onPrint(); } }} tabIndex={0}>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      <p className="text-sm text-ink">{t`${name} is checked in. Print the current event credential and separately consented profile photo.`}</p>
    </div>
  </Modal>;
}
