import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { ActionControl, EmptyState, ListRow, OverflowMenu, RelativeTime, StatusBadge, StatusPill, type Action } from "../../../components/ui";
import type { HardwareRequest } from "./Queues";
import { RequestDetail } from "./RequestDetail";

/** "2 damaged · 1 missing" across the request, so problem loans stand out without opening each one. */
function itemFlags(row: HardwareRequest) {
  const sum = (key: "damaged_quantity" | "missing_quantity" | "needs_fix_quantity") => row.items.reduce((total, item) => total + (item[key] ?? 0), 0);
  const [damaged, missing, fix] = [sum("damaged_quantity"), sum("missing_quantity"), sum("needs_fix_quantity")];
  return [damaged ? `${damaged} damaged` : "", missing ? `${missing} missing` : "", fix ? `${fix} to fix` : ""].filter(Boolean).join(" · ");
}
/** Ready rows list where to fetch each item before the handover. */
function shelves(row: HardwareRequest) {
  return row.status === "accepted" ? [...new Set(row.items.map(item => item.storage_location).filter(Boolean))] : [];
}

export function RequestList({ rows, canViewAudit = false, actions, primary, menu, reject, extra }: {
  rows: HardwareRequest[]; canViewAudit?: boolean; actions?: (row: HardwareRequest) => ReactNode;
  primary?: (row: HardwareRequest) => Action | undefined; menu?: (row: HardwareRequest) => Action[];
  reject?: (row: HardwareRequest) => Action; extra?: (row: HardwareRequest) => ReactNode;
}) {
  const [copyMessage, setCopyMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [params, setParams] = useSearchParams();
  const selected = params.get("request") || params.get("id");
  const detail = rows.find(row => String(row.id) === selected);
  const update = (patch: Record<string, string>) => setParams(current => {
    const next = new URLSearchParams(current);
    Object.entries(patch).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    return next;
  });
  const open = (row: HardwareRequest, requestView = "overview") => update({ request: String(row.id), requestView });
  const copyLink = async (row: HardwareRequest) => {
    try {
      if (!navigator.clipboard) throw new Error(t`Clipboard unavailable`);
      const url = new URL(window.location.href); url.searchParams.set("id", String(row.id));
      url.searchParams.delete("queue"); url.searchParams.delete("request"); url.searchParams.delete("requestView");
      await navigator.clipboard.writeText(url.toString());
      setCopyMessage({ text: t`Request link copied.`, error: false });
    } catch { setCopyMessage({ text: t`Couldn't copy the link. Try again from the request menu.`, error: true }); }
  };
  if (!rows.length) return <EmptyState message={t`No requests here yet. Choose another queue to keep going.`} />;
  return <div className="grid gap-3">{copyMessage ? <p role={copyMessage.error ? "alert" : "status"} className={copyMessage.error ? "text-sm text-danger" : "text-sm text-muted"}>{copyMessage.text}</p> : null}{rows.map(row => {
    const next = primary?.(row);
    const pending = row.status === "pending_approval";
    const flags = itemFlags(row);
    const shelf = shelves(row);
    const identity = !pending && row.return_due_at ? { kind: "date" as const, date: row.return_due_at }
      : { kind: "avatar" as const, name: row.requester_display || row.requester_username, seed: row.requester_username };
    const overflow: Action[] = [
      { label: pending ? t`Review details` : t`View details`, onClick: () => open(row) }, ...(pending && reject ? [reject(row)] : []), ...(menu?.(row) ?? []),
      ...(canViewAudit ? [{ label: t`View timeline`, onClick: () => open(row, "timeline") }] : []),
      ...(row.issue_evidence_id || row.return_evidence_ids?.length ? [{ label: t`View photos`, onClick: () => open(row, "evidence") }] : []),
      { label: t`Copy link`, onClick: () => { void copyLink(row); } },
    ];
    return <article key={row.id} aria-label={t`Request #${row.id}`}>
      <ListRow title={row.requester_display || row.requester_username} identity={identity} onClick={() => open(row)}
        meta={<><span>#{row.id} · {row.items.length} {row.items.length === 1 ? "item" : "items"} · {row.items.slice(0, 2).map(item => `${item.product_name} ×${item.requested_quantity}`).join(", ")}{row.items.length > 2 ? t` · +${row.items.length - 2} more` : ""}</span>
          {row.requested_for ? <span className="mt-1 block break-words">{row.requested_for}</span> : null}
          {shelf.length ? <span className="mt-1 block break-words">{t`Shelf: ${shelf.join(", ")}`}</span> : null}
          {row.rejection_reason ? <span className="mt-1 block break-words">{t`Rejected: ${row.rejection_reason}`}</span> : null}
          {row.status === "accepted" && row.pickup_until ? <span className="mt-1 block">{t`Collect by `}<RelativeTime date={row.pickup_until} /></span> : null}
          {row.return_due_at ? <span className="mt-1 block">{new Date(row.return_due_at).getTime() < Date.now() ? t`Overdue · ` : t`Due `}<RelativeTime date={row.return_due_at} /></span> : null}</>}
        right={<div className="flex flex-wrap items-center gap-2"><StatusBadge status={row.status} />
          {flags ? <StatusPill tone="danger" label={flags} /> : null}
          {next ? <ActionControl primary action={{ ...next, label: row.status === "issued" || row.status === "partially_returned" ? t`Return` : next.label }} />
            : pending ? <ActionControl action={{ label: t`Review`, onClick: () => open(row) }} /> : null}
          {extra?.(row)}{actions?.(row)}<OverflowMenu label={t`More actions for request #${row.id}`} actions={overflow} /></div>} />
    </article>;
  })}
    {detail ? <RequestDetail row={detail} canViewAudit={canViewAudit} primary={primary?.(detail)} secondary={reject?.(detail)}
      menu={menu?.(detail)} extra={extra?.(detail)} view={params.get("requestView") ?? "overview"}
      onView={view => update({ requestView: view })} onClose={() => update({ request: "", id: "", requestView: "", queue: params.get("queue") || (detail.status === "pending_approval" ? "pending" : detail.status === "accepted" ? "accepted" : ["issued", "partially_returned"].includes(detail.status) ? "active" : "history") })} /> : null}
  </div>;
}
