import type { ReactNode } from "react";
import { ListRow, RelativeTime, Skeleton, ErrorBlock, type Action } from "../../../components/ui";
import type { DashboardLayoutProps } from "../../../components/layouts/DashboardLayout";
import { usePaginatedQuery, type Paginated } from "../../../lib/usePaginatedQuery";
import { staffTabPath } from "../staffTabs";
import { useStaffGet, type Makerspace } from "./shared";
import type { HardwareRequest } from "./Queues";
import { RouteLink } from "../../../components/ui/RouteLink";

/** Mirrors `UNRECOGNIZED_LABEL` in backend/apps/audit/presentation_catalog.py. */
const UNRECOGNIZED_AUDIT_LABEL = "Unrecognized audit action";

type Routing = { makerspace: Makerspace; guestOnly: boolean; singleTenantLocked: boolean };
type AuditEntry = { id: number; actor_display: string | null; action_label: string; created_at: string; target_link?: string | null };

// Callbacks fill layout slots while mounting each privileged query only after its gate passes.
export function DashboardActivity({ makerspace, guestOnly, singleTenantLocked, children }: Routing & {
  children: (rail?: DashboardLayoutProps["rail"], sections?: DashboardLayoutProps["main"]) => ReactNode;
}) {
  const query = `makerspace=${makerspace.id}`;
  const activity = useStaffGet<Paginated<AuditEntry>>(["audit", query], `/admin/audit-logs?${query}`);
  const all: Action = { label: "See all activity →", href: staffTabPath("audit", guestOnly, makerspace.slug, singleTenantLocked) };
  // The backend withholds actions its presentation catalogue does not describe; a dashboard rail
  // full of "Unrecognized audit action" says nothing, so only described activity is shown here
  // (the Audit log page still lists every row).
  const readable = (activity.data?.results ?? []).filter(row => row.action_label !== UNRECOGNIZED_AUDIT_LABEL);
  if (activity.isLoading || activity.error || !readable.length) return children(undefined, [{
    title: "Recent activity", action: all, isEmpty: activity.isSuccess && !readable.length,
    empty: { message: "No activity yet. New handovers and updates will appear here." },
    content: activity.error ? <ErrorBlock error={activity.error} resource="recent activity" onRetry={() => { void activity.refetch(); }} />
      : <div role="status" aria-label="Loading recent activity"><Skeleton className="h-24 w-full" /></div>,
  }]);
  return children({ title: "Recent activity", seeAll: all,
    items: readable.slice(0, 8).map(row => ({ key: String(row.id), actor: row.actor_display || "Space Works",
      date: row.created_at, children: row.target_link?.startsWith("/") && !row.target_link.startsWith("//")
        ? <RouteLink className="inline-flex min-h-11 items-center underline focus-visible:outline-2 focus-visible:outline-focus" href={row.target_link}>{row.action_label}</RouteLink>
        : row.action_label })),
  });
}

export function DashboardDueBack({ makerspace, guestOnly, singleTenantLocked, children }: Routing & {
  children: (sections: DashboardLayoutProps["main"]) => ReactNode;
}) {
  const loans = usePaginatedQuery<HardwareRequest>({ key: ["active", makerspace.id],
    path: `/admin/makerspace/${makerspace.id}/active-loans`, page: 1, ordering: "return_due_at" });
  const now = Date.now();
  const dated = loans.results.filter(row => row.return_due_at && Number.isFinite(Date.parse(row.return_due_at)));
  const overdue = dated.filter(row => Date.parse(row.return_due_at!) < now).slice(0, 5);
  const soon = dated.filter(row => Date.parse(row.return_due_at!) >= now && Date.parse(row.return_due_at!) <= now + 3 * 86400000).slice(0, 5);
  const href = `${staffTabPath("requests", guestOnly, makerspace.slug, singleTenantLocked)}?queue=active&ordering=return_due_at`;
  const rows = (items: HardwareRequest[]) => <div className="grid gap-3">{items.map(row => <ListRow key={row.id}
    title={row.requester_display || row.requester_username} identity={{ kind: "date", date: row.return_due_at! }}
    href={`${href}&id=${row.id}`} meta={`Request #${row.id} · ${row.items.map(item => `${item.product_name} × ${item.issued_quantity}`).join(", ")}`}
    right={<RelativeTime date={row.return_due_at!} />} />)}</div>;
  if (loans.isLoading || loans.error) return children([{ title: "Due back", empty: { message: "No loans due in the next 3 days." },
    content: loans.error ? <ErrorBlock error={loans.error} resource="due loans" onRetry={() => { void loans.refetch(); }} />
      : <div role="status" aria-label="Loading due loans"><Skeleton className="h-24 w-full" /></div> }]);
  return children([
    ...(overdue.length ? [{ title: "Overdue", action: { label: "See all →", href }, content: rows(overdue), empty: { message: "No overdue loans." } }] : []),
    { title: "Due within 3 days", action: { label: "See all →", href }, content: rows(soon), isEmpty: !soon.length,
      empty: { message: "Nothing needs you right now. New requests and due-backs will show up here." } },
  ]);
}
