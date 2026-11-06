import { t } from "@lingui/core/macro";
import { Field, Modal } from "../../../../components/ui";
import { REISSUE_REASONS, type MemberCard, type ReissueReason } from "./types";

export function ReissueCardDialog({
  card,
  reason,
  pending,
  error,
  onReasonChange,
  onClose,
  onSubmit,
}: {
  card: MemberCard | null;
  reason: ReissueReason;
  pending: boolean;
  error?: string;
  onReasonChange: (reason: ReissueReason) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <Modal
      open={Boolean(card)}
      onClose={onClose}
      title={t`Reissue card`}
      footer={
        <div className="desk-actions flex flex-wrap justify-end gap-2">
          <button className="desk-button" type="button" disabled={pending} onClick={onClose}>
            {t`Cancel`}</button>
          <button className="desk-button-primary" type="button" disabled={pending} onClick={onSubmit}>
            {pending ? t`Reissuing…` : t`Reissue`}
          </button>
        </div>
      }
    >
      <p className="text-sm text-muted">
        {t`Replaces `}<span className="tabular-nums">{card?.card_number}</span> for {card?.printed_name}. The
        old card stops resolving as soon as the new one is issued.
      </p>
      <Field label={t`Reason`} className="mt-3">
        <select
          className="desk-input"
          value={reason}
          onChange={(event) => onReasonChange(event.target.value as ReissueReason)}
        >
          {REISSUE_REASONS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </Field>
      {error ? (
        <p className="mt-3 text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </Modal>
  );
}

export function RevokeCardDialog({
  card,
  note,
  pending,
  error,
  onNoteChange,
  onClose,
  onSubmit,
}: {
  card: MemberCard | null;
  note: string;
  pending: boolean;
  error?: string;
  onNoteChange: (note: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  // The note is required (3+ characters): it is kept, encrypted, with the card for the audit trail.
  const ready = note.trim().length >= 3;
  return (
    <Modal
      open={Boolean(card)}
      onClose={onClose}
      title={t`Revoke this card?`}
      footer={
        <div className="desk-actions flex flex-wrap justify-end gap-2">
          <button className="desk-button" type="button" disabled={pending} onClick={onClose}>
            {t`Cancel`}</button>
          <button className="desk-button-danger" type="button" disabled={pending || !ready} onClick={onSubmit}>
            {pending ? t`Revoking…` : t`Revoke card`}
          </button>
        </div>
      }
    >
      <p className="text-sm text-muted">
        <span className="tabular-nums">{card?.number_display || card?.card_number}</span> for {card?.printed_name} {t` stops working at the door and on the check page, and its photo is deleted.`}</p>
      <Field label={t`Why is it revoked?`} hint={t`Seen by staff only.`} className="mt-3">
        <input className="desk-input" value={note} maxLength={500} onChange={(event) => onNoteChange(event.target.value)} />
      </Field>
      {error ? (
        <p className="mt-3 text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </Modal>
  );
}

export function PhotoRequestDialog({ card, reason, pending, error, onReasonChange, onClose, onSubmit }: {
  card: MemberCard | null; reason: string; pending: boolean; error?: string;
  onReasonChange: (reason: string) => void; onClose: () => void; onSubmit: () => void;
}) {
  return (
    <Modal open={Boolean(card)} onClose={onClose} title={t`Ask for a new photo?`}
      footer={<div className="desk-actions flex flex-wrap justify-end gap-2">
        <button className="desk-button" type="button" disabled={pending} onClick={onClose}>{t`Cancel`}</button>
        <button className="desk-button-primary" type="button" disabled={pending} onClick={onSubmit}>
          {pending ? t`Sending…` : t`Ask for a new photo`}</button>
      </div>}>
      <p className="text-sm text-muted">{card?.printed_name} {t` is asked to upload a new photo, with one reminder a week later. The card stays valid meanwhile.`}</p>
      <Field label={t`What is wrong with the current one? (optional)`} className="mt-3">
        <input className="desk-input" value={reason} maxLength={300} onChange={(event) => onReasonChange(event.target.value)} />
      </Field>
      {error ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}
    </Modal>
  );
}
