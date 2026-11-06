import { useState } from "react";
import { ListRow, RelativeTime, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import type { HealthCard } from "../platformSpaces/spacesApi";
import { useArchiveKeyJob, type StaleArchive } from "./spaceKeysApi";
import { TypedConfirmDialog } from "./TypedConfirmDialog";

const STATE = { queued: ["Queued", "neutral"], running: ["Working", "warn"], done: ["Done", "success"], failed: ["Failed", "danger"] } as const;
type Pending = { row: StaleArchive; action: "reencrypt" | "purge" };

/** This space's own archives still on a retired backup key: re-encrypt to today's keys, or purge. */
export function StaleArchivesList({ card, rows }: { card: HealthCard; rows: StaleArchive[] }) {
  const job = useArchiveKeyJob(card.id);
  const [pending, setPending] = useState<Pending | null>(null);
  const open = (next: Pending) => { job.reset(); setPending(next); };
  if (!rows.length) return <p className="text-sm text-muted">No archive of this space is on a retired backup key.</p>;
  return <div className="grid gap-2">
    {rows.map(row => {
      const state = row.job ? STATE[row.job.state] : null;
      const working = row.job?.state === "queued" || row.job?.state === "running";
      return <ListRow key={row.id} title={`Archive ${row.id.slice(0, 8)}`}
        meta={<>{row.completed_at ? <>made <RelativeTime date={row.completed_at} exact /></> : "not finished"}
          {row.job?.error_code ? ` · ${row.job.error_code}` : ""}</>}
        right={<div className="flex flex-wrap items-center gap-2">
          {state ? <StatusPill label={`${row.job?.action === "purge" ? "Purge" : "Re-encrypt"}: ${state[0]}`} tone={state[1]} /> : null}
          {row.reencryptable ? <button type="button" className="desk-button" disabled={working}
            onClick={() => open({ row, action: "reencrypt" })}>Re-encrypt…</button> : null}
          <button type="button" className="desk-button-danger-outline" disabled={working}
            onClick={() => open({ row, action: "purge" })}>Purge…</button>
        </div>} />;
    })}
    {pending ? <TypedConfirmDialog title={pending.action === "purge" ? "Purge this archive" : "Re-encrypt this archive"}
      confirmLabel={pending.action === "purge" ? "Purge for good" : "Re-encrypt"} expected={card.slug} what="space's web address name"
      message={pending.action === "purge" ? "The archive's files are deleted now. It can no longer be restored."
        : "The archive is opened with this server's key and written again to today's keys, in the background."}
      pending={job.isPending} error={job.error} onCancel={() => setPending(null)}
      onConfirm={typed => job.mutate({ archiveId: pending.row.id, action: pending.action, confirm_slug: typed },
        { onSuccess: () => { toast("Archive job queued."); setPending(null); } })} /> : null}
  </div>;
}
