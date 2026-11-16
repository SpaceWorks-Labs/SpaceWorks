// Removing a plan or title design (decision 219(h)): a design that was never published is
// deleted; one that reached members is archived -- members fall back to the next design and its
// history is kept -- and can be restored from the archived list.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { CardDesign } from "../../../../components/card-designer/cardTypes";
import { ConfirmDialog, ErrorBlock } from "../../../../components/ui";
import { useArchivedCardDesigns, useRemoveCardOverride } from "./apiCards";

export function RemoveDesignButton({ makerspaceId, design, onRemoved }: {
  makerspaceId: number; design: CardDesign; onRemoved: () => void;
}) {
  const remove = useRemoveCardOverride(makerspaceId);
  const [confirming, setConfirming] = useState(false);
  const archive = Boolean(design.published_at);
  return <>
    <button type="button" className="desk-button min-h-11" onClick={() => setConfirming(true)}>
      {archive ? t`Archive design` : t`Delete design`}</button>
    {remove.error ? <ErrorBlock error={remove.error} /> : null}
    <ConfirmDialog open={confirming} tone="danger" pending={remove.isPending}
      title={archive ? t`Archive ${design.target_label} design?` : t`Delete ${design.target_label} design?`}
      message={archive
        ? t`Members on it switch to the next design (plan, then space default). The design and its history are kept and you can restore it.`
        : t`This design was never published, so no member has it. It is deleted for good.`}
      confirmLabel={archive ? t`Archive` : t`Delete`} onCancel={() => setConfirming(false)}
      onConfirm={() => remove.mutate({ design, action: archive ? "archive" : "delete" },
        { onSuccess: () => { setConfirming(false); onRemoved(); } })} />
  </>;
}

export function ArchivedDesigns({ makerspaceId, canEdit, onRestored }: {
  makerspaceId: number; canEdit: boolean; onRestored: (id: number) => void;
}) {
  const archived = useArchivedCardDesigns(makerspaceId);
  const restore = useRemoveCardOverride(makerspaceId);
  const rows = archived.data ?? [];
  if (!rows.length) return null;
  return <details className="rounded-lg border border-line p-3">
    <summary className="cursor-pointer text-sm font-semibold text-ink">{t`Archived designs (${rows.length})`}</summary>
    <ul className="mt-3 grid gap-2" aria-label={t`Archived designs`}>
      {rows.map((row) => <li key={row.id} className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-ink">{row.target_label}</span>
        {canEdit ? <button type="button" className="desk-button min-h-11" disabled={restore.isPending}
          onClick={() => restore.mutate({ design: row, action: "unarchive" }, { onSuccess: () => onRestored(row.id) })}>
          {t`Restore`}</button> : null}
      </li>)}
    </ul>
    {restore.error ? <ErrorBlock error={restore.error} /> : null}
  </details>;
}
