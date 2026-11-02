import type { ReactNode } from "react";
import { DetailLayout } from "../../../components/layouts";
import { KeyValueCard, ListRow, RelativeTime, StatusBadge, type Action } from "../../../components/ui";
import { StatusStepper } from "../../../components/ui/StatusStepper";
import { RequestTimelineBlock } from "./LoanTimeline";
import type { HardwareRequest } from "./Queues";
import { RequestEvidence } from "./RequestEvidence";
import { LoanChargesPanel } from "../loanCharges/LoanChargesPanel";

type Actor = { username: string; role: string };
export function RequestDetail({ row, canViewAudit, primary, secondary, menu, extra, view, onView, onClose }: {
  row: HardwareRequest; canViewAudit: boolean; primary?: Action; secondary?: Action; menu?: Action[]; extra?: ReactNode;
  view: string; onView: (view: string) => void; onClose: () => void;
}) {
  const active = ["overview", "evidence", ...(canViewAudit ? ["timeline"] : [])].includes(view) ? view : "overview";
  const actors = row as HardwareRequest & { accepted_by?: Actor; issued_by?: Actor };
  const tabs = ["overview", "evidence", ...(canViewAudit ? ["timeline"] : [])].map(key => {
    const url = new URL(window.location.href); url.searchParams.set("requestView", key);
    return { key, label: key[0].toUpperCase() + key.slice(1), href: url.pathname + url.search };
  });
  return <div onClickCapture={event => {
    const anchor = (event.target as HTMLElement).closest('nav[aria-label="Page sections"] a');
    if (!anchor || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const next = new URL((anchor as HTMLAnchorElement).href).searchParams.get("requestView");
    if (next) { event.preventDefault(); event.stopPropagation(); onView(next); }
  }}><DetailLayout presentation="drawer" open onClose={onClose} drawerWidth={640}
    title={`Request #${row.id}`} identity={{ kind: "avatar", name: row.requester_display || row.requester_username, seed: row.requester_username }}
    status={<StatusBadge status={row.status} />} meta={[row.requester_display || row.requester_username,
      row.return_due_at ? <span>Due <RelativeTime date={row.return_due_at} /></span> : "No due date set"]}
    actions={{ overflow: menu }} tabs={tabs} activeTab={active} state={{ status: "ready" }}
    main={active === "evidence" ? <RequestEvidence row={row} /> : active === "timeline" ? <RequestTimelineBlock requestId={row.id} /> : <div className="grid gap-6">
      {row.status === "cancelled" || row.status === "expired" ? <p className="rounded-xl border border-line p-4 text-sm text-muted">{row.status === "expired"
        ? "Expired: it was not collected before the pickup deadline, so its items went back on the shelf." : "Cancelled before it was handed over."}</p> : <StatusStepper status={row.status} />}
      <section aria-label="Items"><h2 className="title-panel mb-3">Items</h2><div className="grid gap-3">{row.items.map(item => <ListRow key={item.id} title={item.product_name}
        meta={<>{item.storage_location ? `Shelf: ${item.storage_location} · ` : ""}{item.requires_asset_qr ? "QR-tracked" : "Quantity-tracked"}</>}
        right={<span className="tabular-nums">{row.status === "pending_approval" ? item.requested_quantity : row.status === "accepted" ? item.accepted_quantity : item.issued_quantity} / {item.requested_quantity}</span>} />)}</div></section>
      {row.status === "rejected" && row.rejection_reason ? <p className="rounded-xl border border-danger-line p-4 text-danger">Rejected: {row.rejection_reason}</p> : null}
      {row.items.some(item => item.damaged_quantity || item.missing_quantity || item.needs_fix_quantity) ? <div className="rounded-xl border border-danger-line p-4 text-danger"><h2 className="title-section">Items needing attention</h2>
        {row.items.filter(item => item.damaged_quantity || item.missing_quantity || item.needs_fix_quantity).map(item => <p key={item.id}>{item.product_name}: {item.damaged_quantity} damaged · {item.missing_quantity} missing · {item.needs_fix_quantity} to-fix</p>)}</div> : null}
      {extra}
      <LoanChargesPanel loan={row} />
    </div>}
    aside={active === "overview" ? <KeyValueCard items={[
      { label: "Purpose", value: <span className="break-words">{row.requested_for || "No note"}</span> },
      { label: "Contact", value: <span className="break-words">{[row.requester_contact_email, row.requester_contact_phone].filter(Boolean).join(" · ") || "No contact details"}</span> },
      { label: "Box", value: row.assigned_box_label || row.assigned_box?.label || "Not assigned" },
      ...(actors.accepted_by ? [{ label: "Accepted by", value: formatActor(actors.accepted_by) }] : []),
      ...(actors.issued_by ? [{ label: "Issued by", value: formatActor(actors.issued_by) }] : []),
      ...(row.return_reminder_sent_at ? [{ label: "Reminder sent", value: <RelativeTime date={row.return_reminder_sent_at} /> }] : []),
      ...(row.pickup_from ? [{ label: "Collect from", value: new Date(row.pickup_from).toLocaleString() }] : []),
      ...(row.pickup_until ? [{ label: "Pickup deadline", value: new Date(row.pickup_until).toLocaleString() }] : []),
    ]} /> : undefined}
    footer={{ primary, secondary: secondary ? [secondary] : [] }} />
  </div>;
}
function formatActor(actor: Actor) { return actor.role ? `${actor.username} (${actor.role})` : actor.username; }
