import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { ListLayout } from "../../../components/layouts";
import { ListRow } from "../../../components/ui";
import { openSpaceTab } from "./openSpaceTab";
import { crossSpaceKeys, getInbox } from "./crossSpaceApi";

/**
 * Decision 242(l) / U9: unread notifications across every space, before choosing one. Counts only;
 * opening a space takes the superadmin to that space's own inbox. The read is audited server-side.
 */
export function PlatformInboxPage() {
  const inbox = useQuery({ queryKey: crossSpaceKeys.inbox, queryFn: getInbox, refetchInterval: 120_000 });
  const rows = [...inbox.data?.spaces ?? []].sort((a, b) => (b.personal_unread + b.notices_unread) - (a.personal_unread + a.notices_unread));
  return <ListLayout header={{ title: t`Inbox across spaces`, subtitle: t`Unread notifications in each space. Open a space to read them there.`,
    meta: inbox.data ? t`${inbox.data.total} unread in total` : undefined }}
    state={inbox.isLoading ? { status: "loading" } : inbox.isError
      ? { status: "error", error: t`Couldn't load the inbox. Try again.`, onRetry: () => { void inbox.refetch(); } } : { status: "ready" }}
    isEmpty={inbox.isSuccess && !rows.length} empty={{ message: t`You're all caught up. Nothing is unread in any space.` }}
    body={{ kind: "rows", rows: rows.map(row => <ListRow key={row.id} title={row.name}
      meta={t`For you: ${row.personal_unread} · Space notices: ${row.notices_unread}`}
      right={<button type="button" className="desk-button min-h-11" onClick={() => openSpaceTab(row.id, "/admin/notifications")}>{t`Open inbox`}</button>} />) }} />;
}
