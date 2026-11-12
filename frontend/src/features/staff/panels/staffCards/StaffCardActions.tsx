// The per-card actions of the staff list: download, reissue, revoke (with a reason) and desk print.
// Revoke asks for a reason from a short list (the server keeps it with the card, up to 32 characters).
import { plural, t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ErrorBlock, Field, Modal } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import { staffRequestBlob } from "../../../../lib/api";
import { DeskPrintDialog, type DeskPrintTarget } from "../../../cards/deskPrint/DeskPrintDialog";
import { useDeskPrintQueue } from "../../../cards/deskPrint/useDeskPrintQueue";
import { downloadPdf } from "../memberCards/api";
import { useReissueStaffCard, useRevokeStaffCard, staffCardKeys } from "./api";
import type { StaffCardHolder } from "./types";
import { BoxArt } from "../../../../components/BoxSpinner";

const REASONS = (): { value: string; label: string }[] => [
  { value: "left", label: t`Left the team` }, { value: "lost", label: t`Lost` }, { value: "stolen", label: t`Stolen` },
  { value: "damaged", label: t`Damaged` }, { value: "revoked", label: t`Other` },
];

function RevokeDialog({ holder, pending, error, onClose, onSubmit }: {
  holder: StaffCardHolder | null; pending: boolean; error: unknown; onClose: () => void; onSubmit: (reason: string) => void;
}) {
  const [reason, setReason] = useState("left");
  return <Modal open={Boolean(holder)} onClose={onClose} title={t`Revoke this staff card?`}
    footer={<div className="desk-actions flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button" disabled={pending} onClick={onClose}>{t`Cancel`}</button>
      <button type="button" className="desk-button-danger" disabled={pending} onClick={() => onSubmit(reason)}>
        {pending ? <><BoxArt size={16} mono />{t`Revoking…`}</> : t`Revoke card`}</button>
    </div>}>
    <p className="text-sm text-muted">{t`${holder?.card?.number ?? ""} for ${holder?.name ?? ""} stops working at once and its check page shows it as revoked.`}</p>
    <Field label={t`Why is it revoked?`} className="mt-3">
      <select className="desk-input min-h-11" value={reason} onChange={(event) => setReason(event.target.value)}>
        {REASONS().map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </Field>
    {error ? <div className="mt-3"><ErrorBlock error={error} /></div> : null}
  </Modal>;
}

export function useStaffCardActions(makerspaceId: number, deskPrint: boolean) {
  const client = useQueryClient();
  const reissue = useReissueStaffCard(makerspaceId);
  const revoke = useRevokeStaffCard(makerspaceId);
  const queue = useDeskPrintQueue();
  const [revoking, setRevoking] = useState<StaffCardHolder | null>(null);
  const [printing, setPrinting] = useState<DeskPrintTarget | null>(null);
  const download = useMutation({
    mutationFn: async ({ holder, format }: { holder: StaffCardHolder; format: "pdf" | "png" }) => {
      const blob = await staffRequestBlob(`/admin/staff-cards/${holder.card?.id}/download?format=${format}&side=front`);
      downloadPdf(blob, `staff-card-${holder.card?.number ?? holder.membership_id}.${format}`);
    },
  });

  const doReissue = (holder: StaffCardHolder) => holder.card && reissue.mutate(holder.card.id, {
    onSuccess: () => toast(t`New card made for ${holder.name}. Reprint it; the old one no longer works.`, { tone: "success" }),
  });
  const actions = (holder: StaffCardHolder) => {
    const card = holder.card;
    if (!card || card.status !== "valid") return [];
    return [
      ...(deskPrint ? [{ label: t`Print at desk`, onClick: () => setPrinting({ id: `staff:${card.id}`, label: `${holder.name} ${card.number}`,
        facePath: `/admin/staff-cards/${card.id}/print-face` }) }] : []),
      { label: t`Download PDF`, onClick: () => download.mutate({ holder, format: "pdf" }) },
      { label: t`Download PNG`, onClick: () => download.mutate({ holder, format: "png" }) },
      { label: t`Reissue`, confirm: { title: t`Reissue this card?`, message: t`${holder.name} gets a new QR on the same number. The old card stops working.`, confirmLabel: t`Reissue` },
        onClick: () => doReissue(holder) },
      { label: t`Revoke`, tone: "danger" as const, onClick: () => { revoke.reset(); setRevoking(holder); } },
    ];
  };

  const dialogs = <>
    {download.error || reissue.error ? <ErrorBlock error={download.error ?? reissue.error} /> : null}
    <RevokeDialog holder={revoking} pending={revoke.isPending} error={revoke.error} onClose={() => setRevoking(null)}
      onSubmit={(reason) => revoking?.card && revoke.mutate({ cardId: revoking.card.id, reason }, { onSuccess: () => setRevoking(null) })} />
    <DeskPrintDialog target={printing} queue={queue} onClose={() => setPrinting(null)}
      onPrinted={() => void client.invalidateQueries({ queryKey: staffCardKeys.all(makerspaceId) })} />
  </>;
  const printSelected = (holders: StaffCardHolder[]) => setPrinting({
    id: `staff-batch:${holders.map((holder) => holder.card?.id).join(",")}`,
    label: plural(holders.length, { one: "# staff card", other: "# staff cards" }),
    facePaths: holders.map((holder) => `/admin/staff-cards/${holder.card?.id}/print-face`) });
  return { actions, dialogs, printSelected, reissue: doReissue, reissuing: reissue.isPending };
}
