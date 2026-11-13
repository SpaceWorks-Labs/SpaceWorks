import { t } from "@lingui/core/macro";
import { useState } from "react";
import { EmptyState, ErrorText, ListRow, Pagination, RelativeTime, StatusPill, type Tone } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import { ActionDialog } from "../../platformSpaces/ActionDialog";
import { PAGE_SIZE } from "../../platformParity/parityRequest";
import { useRehydrate, useUploads, type Destination, type Upload } from "./offsiteApi";
import { LogoLoader } from "../../../../components/LogoLoader";

const STATES: Record<string, [string, Tone]> = {
  pending: ["Pending", "neutral"], uploading: ["Uploading", "info"], bytes_verified: ["Verified copy", "success"],
  abandoned: ["Abandoned", "warn"], deleted: ["Deleted by retention", "neutral"],
};

function RehydrateDialog({ upload, destination, onClose }: { upload: Upload; destination: Destination; onClose: () => void }) {
  const rehydrate = useRehydrate();
  return <ActionDialog title={t`Restore the primary copy`} confirmLabel={t`Restore primary copy`} pending={rehydrate.isPending}
    error={rehydrate.error} onCancel={onClose}
    message={t`Copies this verified offsite copy back to the backup store, for an archive whose primary bytes are missing. It changes no live data; restore the space or platform from the archive afterwards.`}
    onSubmit={() => rehydrate.mutate({ archiveId: upload.archive_id_snapshot, destination: destination.id },
      { onSuccess: () => { toast(t`Restore of the primary copy started.`); onClose(); } })} />;
}

/** One destination's upload journal: what was copied, verified, abandoned or expired. */
export function OffsiteUploads({ destination }: { destination: Destination }) {
  const [page, setPage] = useState(1);
  const [restoring, setRestoring] = useState<Upload | null>(null);
  const list = useUploads(destination.id, page);
  const rows = list.data?.results ?? [];
  if (list.isLoading) return <LogoLoader size={48} className="min-h-20 py-3" />;
  if (list.isError) return <ErrorText resource={t`offsite uploads`} onRetry={() => { void list.refetch(); }} />;
  return <div className="grid gap-3">
    {!rows.length ? <EmptyState message={t`Nothing has been copied here yet. New backups are pushed on the schedule, or press Push now.`} />
      : rows.map(upload => {
        const [label, tone] = STATES[upload.state] ?? [upload.state, "neutral"];
        const scope = upload.scope_snapshot === "makerspace" && upload.makerspace_id_snapshot ? t`Space #${upload.makerspace_id_snapshot}` : t`Whole platform`;
        return <ListRow key={upload.id} title={`${scope} · ${upload.archive_id_snapshot.slice(0, 8)}`}
          meta={<>{upload.verified_at ? <>{t`verified `}<RelativeTime date={upload.verified_at} exact /></> : upload.uploaded_at
            ? <>{t`uploaded `}<RelativeTime date={upload.uploaded_at} exact /></> : t`${upload.attempts} attempts`}
            {upload.expires_at ? <>{t` · expires `}<RelativeTime date={upload.expires_at} exact /></> : null}
            {upload.last_error_code ? ` · ${upload.last_error_code}` : ""}</>}
          right={<div className="flex flex-wrap items-center gap-2"><StatusPill label={label} tone={tone} />
            {upload.state === "bytes_verified" && !destination.retired_at ? <button type="button" className="desk-button"
              onClick={() => setRestoring(upload)}>{t`Restore primary…`}</button> : null}</div>} />;
      })}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {restoring ? <RehydrateDialog upload={restoring} destination={destination} onClose={() => setRestoring(null)} /> : null}
  </div>;
}
