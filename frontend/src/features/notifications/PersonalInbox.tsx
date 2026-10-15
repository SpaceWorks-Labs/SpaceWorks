import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListLayout } from "../../components/layouts";
import { ErrorBlock, ListRow, RelativeTime, StatusPill, type Action, type IconName } from "../../components/ui";
import { RouteLink } from "../../components/ui/RouteLink";
import { memberRequest, staffRequest } from "../../lib/api";
import { opsQueryState, useOpsTabs } from "../staff/opsPresentation";
import { inboxUnreadKey, personalRecipientKey } from "./personalQueryKeys";
export { inboxUnreadKey } from "./personalQueryKeys";

export type InboxRow = {
  id: number; feature: string; event: string; title: string; summary: string; link: string;
  read_at: string | null; created_at: string;
};
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
const families: Record<string, string> = { hardware_requests: "Hardware", printing: "Printing", events: "Events",
  bookings: "Bookings", maintenance: "Maintenance", members: "Members", payments: "Payments", stock: "Stock",
  certifications: "Certifications", devices: "Devices", api_access: "API access" };

const familyIcons: Record<string, IconName> = { hardware_requests: "Wrench", printing: "Settings", events: "Calendar",
  bookings: "Calendar", maintenance: "Wrench", members: "User", payments: "Info", stock: "Wrench",
  certifications: "CheckCircle", devices: "Settings", api_access: "Settings" };

export function isInboxLink(value: string): boolean {
  return value.startsWith("/") && !value.startsWith("//") && !/[\\\x00-\x1f\x7f]/.test(value);
}
function dateGroup(value: string) {
  const date = new Date(value);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (date >= today) return "Today";
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date >= yesterday) return "Yesterday";
  const week = new Date(today);
  week.setDate(week.getDate() - 7);
  return date >= week ? "Earlier this week" : "Older";
}

/** The server decides the page size: a page with a `next` link is full, and the last page's size follows from the count. */
function serverPageSize(data: Page<unknown>, page: number) {
  const length = data.results.length;
  if (data.next || page === 1) return Math.max(1, length);
  return Math.max(1, Math.round((data.count - length) / (page - 1)));
}

export function PersonalInbox({ makerspaceId, member = false, announcement }: {
  makerspaceId: number; member?: boolean; announcement?: Action;
}) {
  const client = useQueryClient();
  const send = member ? memberRequest : staffRequest;
  const mode = member ? "member" : "staff";
  const recipient = personalRecipientKey();
  const tabs = useOpsTabs("inbox", [{ key: "unread", label: "Unread" }, { key: "all", label: "All" }], "all");
  const unread = tabs.active === "unread";
  const [pageState, setPage] = useState({ page: 1, tab: tabs.active });
  const page = pageState.tab === tabs.active ? pageState.page : 1;
  useEffect(() => { setPage({ page: 1, tab: tabs.active }); }, [tabs.active]);
  const [feature, setFeature] = useState("");
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const path = `/notifications/inbox/${makerspaceId}`;
  const params = new URLSearchParams({ page: String(page), unread: String(unread) });
  if (feature) params.set("feature", feature);
  const rows = useQuery({ queryKey: ["notifications-inbox", makerspaceId, mode, recipient, page, unread, feature],
    queryFn: () => send<Page<InboxRow>>(`${path}?${params}`), refetchInterval: 60_000 });
  const count = useQuery({ queryKey: inboxUnreadKey(makerspaceId, mode),
    queryFn: () => send<{ count: number }>(`${path}/unread-count`), refetchInterval: 60_000 });
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["notifications-inbox", makerspaceId, mode, recipient] });
    client.invalidateQueries({ queryKey: inboxUnreadKey(makerspaceId, mode) });
  };
  const read = useMutation({ mutationFn: (id: number) => send(`${path}/${id}/read`, { method: "POST" }), onSuccess: refresh });
  const readAll = useMutation({ mutationFn: () => send(`${path}/read-all`, { method: "POST" }), onSuccess: refresh });
  const unreadCount = count.data?.count ?? 0;
  const state = opsQueryState({ isLoading: rows.isLoading || count.isLoading, error: rows.error ?? count.error,
    refetch: () => Promise.all([rows.refetch(), count.refetch()]) }, "notifications");
  let previousGroup = "";
  return <section aria-label="Personal notifications" onClickCapture={tabs.onClickCapture}>
    <ListLayout header={{ title: member ? "Your inbox" : "Notifications", subtitle: "Activity from your Space Works community.",
      meta: <span aria-live="polite">({unreadCount} unread)</span>,
      primary: { label: "Mark all read", onClick: () => readAll.mutate(), pending: readAll.isPending, pendingLabel: "Marking read…",
        disabled: !unreadCount, disabledReason: !unreadCount ? "You're all caught up." : undefined }, secondary: announcement }}
      tabs={tabs.tabs.map(tab => tab.key === "unread" ? { ...tab, count: unreadCount } : tab)} activeTab={tabs.active}
      filters={{ controls: <label className="grid gap-1 text-sm">Family<select className="desk-input" value={feature}
        onChange={event => { setFeature(event.target.value); setPage({ page: 1, tab: tabs.active }); }}>
        <option value="">All families</option>{Object.entries(families).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label> }} state={state} isEmpty={rows.data?.results.length === 0}
      empty={{ message: unread ? "You're all caught up." : "No notifications yet. Activity from your space shows up here." }}
      filtered={Boolean(feature)} filteredEmpty={{ message: "No notifications in this family. Try another family.", action: { label: "Clear filters", onClick: () => setFeature("") } }}
      body={{ kind: "rows", rows: rows.data?.results.map(row => {
        const group = dateGroup(row.created_at);
        const showGroup = previousGroup !== group;
        previousGroup = group;
        return <div key={row.id} className="grid gap-3">{showGroup ? <h2 className="eyebrow mt-3">{group}</h2> : null}
          <div className={row.read_at ? "" : "rounded-xl border-l-4 border-accent"}>
            <ListRow title={row.title} identity={{ kind: "icon", icon: familyIcons[row.feature] ?? "Info", tone: "neutral" }}
              onClick={!row.read_at ? () => read.mutate(row.id) : undefined}
              meta={<><span>{families[row.feature] ?? row.feature.replace(/_/g, " ")} · <RelativeTime date={row.created_at} /></span>
                <span className="mt-1 block line-clamp-2 whitespace-pre-wrap break-words">{row.summary}</span></>}
              right={<div className="flex flex-wrap items-center gap-2">{!row.read_at ? <StatusPill label="Unread" tone="accent" /> : null}
                {isInboxLink(row.link) ? <RouteLink className="desk-button" href={row.link} onClick={() => { if (!row.read_at) read.mutate(row.id); }}>Open</RouteLink> : null}
                {!row.read_at ? <button className="desk-button" disabled={read.isPending} onClick={() => read.mutate(row.id)}>Mark read</button> : null}</div>} />
            {row.summary ? <div className="mx-4 mb-4">
              <button className="desk-button-ghost" aria-expanded={Boolean(expanded[row.id])}
                onClick={() => { setExpanded(current => ({ ...current, [row.id]: !current[row.id] }));
                  if (!row.read_at && !read.isPending) read.mutate(row.id); }}>
                {expanded[row.id] ? "Show less" : "Read message"}</button>
              {expanded[row.id] ? <p className="whitespace-pre-wrap break-words text-sm">{row.summary}</p> : null}
            </div> : null}
          </div></div>;
      }) }} pagination={rows.data ? { page, pageSize: serverPageSize(rows.data, page), count: rows.data.count,
        onChange: next => setPage({ page: next, tab: tabs.active }) } : undefined}
      detail={read.error || readAll.error ? <ErrorBlock error={read.error ?? readAll.error} /> : undefined} />
  </section>;
}
