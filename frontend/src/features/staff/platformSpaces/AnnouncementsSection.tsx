import { t } from "@lingui/core/macro";
import { useState } from "react";
import { CollapsibleSection, EmptyState, ErrorText, ListRow, Pagination, RelativeTime, StatusPill, type Tone } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "./ActionDialog";
import { AnnouncementForm } from "./AnnouncementForm";
import { severityLabels, useAnnouncements, useCancelAnnouncement, type Announcement } from "./announcementsApi";
import { PAGE_SIZE } from "./spacesApi";
import { LogoLoader } from "../../../components/LogoLoader";

const STATUS: Record<Announcement["status"], [string, Tone]> = {
  scheduled: ["Scheduled", "info"], live: ["Live", "success"], ended: ["Ended", "neutral"], cancelled: ["Cancelled", "neutral"],
};

function CancelDialog({ row, onClose }: { row: Announcement; onClose: () => void }) {
  const cancel = useCancelAnnouncement();
  return <ActionDialog title={t`Cancel this announcement`} confirmLabel={t`Cancel announcement`} tone="danger" pending={cancel.isPending}
    error={cancel.error} onCancel={onClose} message={t`"${row.title}" stops showing right away. Emails already sent cannot be recalled.`}
    onSubmit={() => cancel.mutate(row.id, { onSuccess: () => { toast(t`Announcement cancelled.`); onClose(); } })} />;
}

function audience(row: Announcement) {
  if (row.audience === "all_spaces") return "Every space";
  return row.makerspaces.map(space => space.name).join(", ") || "Selected spaces";
}

/** Platform announcements: compose one, see what is live or scheduled, cancel one. */
export function AnnouncementsSection() {
  const [page, setPage] = useState(1);
  const [cancelling, setCancelling] = useState<Announcement | null>(null);
  const [composing, setComposing] = useState(false);
  const list = useAnnouncements(page);
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <CollapsibleSection title={t`New announcement`} open={composing} onToggle={() => setComposing(!composing)}><AnnouncementForm /></CollapsibleSection>
    {list.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" />
      : list.isError ? <ErrorText resource={t`announcements`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`No announcements yet.`} />
      : <div className="grid gap-3">{rows.map(row => <ListRow key={row.id} title={row.title}
        meta={<>{t`${severityLabels()[row.severity] ?? row.severity} · ${audience(row)} · starts `}<RelativeTime date={row.starts_at} exact />
          {row.ends_at ? <> {t` · ends `}<RelativeTime date={row.ends_at} exact /></> : null}
          {row.email_sent_at ? t` · emailed to ${row.email_recipient_count}` : row.send_email ? t` · email pending` : ""}
          {row.show_to_members ? t` · members see it` : ""}</>}
        right={<div className="flex flex-wrap items-center gap-2">
          <StatusPill label={STATUS[row.status][0]} tone={STATUS[row.status][1]} />
          {row.status === "live" || row.status === "scheduled" ? <button type="button" className="desk-button-danger-outline"
            aria-label={t`Cancel ${row.title}`} onClick={() => setCancelling(row)}>{t`Cancel…`}</button> : null}
        </div>} />)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {cancelling ? <CancelDialog row={cancelling} onClose={() => setCancelling(null)} /> : null}
  </div>;
}
