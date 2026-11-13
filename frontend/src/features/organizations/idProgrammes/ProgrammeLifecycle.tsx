// Removing a programme (decision 219(h)): one that never approved a card is deleted; one that
// did is archived -- closed, out of the active list, every card and its history kept -- and can
// be restored. The server decides; the counts only choose which button to offer first.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ConfirmDialog, ErrorBlock, StatusPill } from "../../../components/ui";
import { useProgrammeLifecycle, type Programme } from "./api";

export function ProgrammeArchivedBanner({ programme }: { programme: Programme }) {
  const lifecycle = useProgrammeLifecycle(programme.id);
  if (!programme.archived_at) return null;
  return <div role="status" className="flex flex-wrap items-center gap-3 rounded-control border border-line bg-surface p-3 text-sm">
    <StatusPill tone="neutral" label={t`Archived`} />
    <span className="min-w-0 flex-1 text-muted">{t`This programme is closed and archived. Its cards are kept and still check as valid until revoked or expired.`}</span>
    {programme.can_manage ? <button type="button" className="desk-button min-h-11" disabled={lifecycle.isPending}
      onClick={() => lifecycle.mutate("unarchive")}>{t`Restore`}</button> : null}
    {lifecycle.error ? <div className="basis-full"><ErrorBlock error={lifecycle.error} /></div> : null}
  </div>;
}

export function RemoveProgramme({ programme, onDeleted }: { programme: Programme; onDeleted: () => void }) {
  const lifecycle = useProgrammeLifecycle(programme.id);
  const [confirming, setConfirming] = useState(false);
  if (programme.archived_at) return null;
  const used = programme.counts.approved + programme.counts.revoked > 0;
  return <section className="grid gap-2 rounded-lg border border-line p-3" aria-label={t`Remove programme`}>
    <h3 className="text-sm font-semibold text-ink">{used ? t`Archive programme` : t`Delete programme`}</h3>
    <p className="text-sm text-muted">{used
      ? t`Cards were issued here, so the programme is archived rather than deleted: joining closes, it leaves the list, and every card is kept.`
      : t`No card was ever approved here, so the programme and its requests can be deleted for good.`}</p>
    <div><button type="button" className="desk-button-danger min-h-11" onClick={() => setConfirming(true)}>
      {used ? t`Archive programme` : t`Delete programme`}</button></div>
    {lifecycle.error ? <ErrorBlock error={lifecycle.error} /> : null}
    <ConfirmDialog open={confirming} tone="danger" pending={lifecycle.isPending}
      title={used ? t`Archive ${programme.name}?` : t`Delete ${programme.name}?`}
      message={used ? t`You can restore it from the archived list later.` : t`This cannot be undone.`}
      confirmLabel={used ? t`Archive` : t`Delete`} onCancel={() => setConfirming(false)}
      onConfirm={() => lifecycle.mutate(used ? "archive" : "delete", {
        onSuccess: () => { setConfirming(false); if (!used) onDeleted(); },
        onError: () => setConfirming(false),
      })} />
  </section>;
}
