import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { EmptyState, Modal, Tabs } from "../../../../components/ui";
import type { MachineServiceRequest } from "../../../../generated/api";

// "Active" (everything not yet finished) is the default so running and ready jobs are never hidden
// behind an empty Pending tab — the pre-revamp console listed every job at once.
const ACTIVE = new Set(["pending", "changes_requested", "quoted", "accepted", "in_progress", "completed", "failed"]);
const statuses = [
  { key: "active", label: t`Active` }, { key: "pending", label: t`Pending` },
  { key: "changes_requested", label: t`Needs changes` }, { key: "quoted", label: t`Quote sent` }, { key: "accepted", label: t`Accepted` },
  { key: "in_progress", label: t`In progress` }, { key: "completed", label: t`Ready` },
  { key: "collected", label: t`Collected` }, { key: "uncollected", label: t`Not collected` }, { key: "failed", label: t`Failed` },
  { key: "rejected", label: t`Rejected` }, { key: "cancelled", label: t`Cancelled` }, { key: "all", label: t`All jobs` },
];
/** Status keys a `?job_status=` deep link may open (dashboard work queues link straight to one). */
export const serviceQueueStatusKeys = statuses.map(item => item.key);
const matches = (key: string, status: string) => key === "all" || (key === "active" ? ACTIVE.has(status) : status === key);
const emptyCopy: Record<string, string> = {
  active: t`No jobs waiting, running or needing a reprint. New requests land here.`, all: t`No jobs yet. New requests land here.`,
};
export function ServiceQueueTabs({ rows, children, initialStatus = "active" }: {
  rows: MachineServiceRequest[] | undefined; children: (rows: MachineServiceRequest[] | undefined) => ReactNode; initialStatus?: string;
}) {
  const [status, setStatus] = useState(serviceQueueStatusKeys.includes(initialStatus) ? initialStatus : "active");
  const visible = rows?.filter(row => matches(status, row.status));
  return <div className="grid gap-4"><Tabs activeKey={status} label={t`Job status`} onChange={setStatus}
    tabs={statuses.map(item => ({ ...item, href: "#", count: rows?.filter(row => matches(item.key, row.status)).length }))}>
    {visible?.length === 0 ? <EmptyState message={emptyCopy[status] ?? t`No jobs in this state.`} /> : children(visible)}
  </Tabs></div>;
}

/** `logging` is owned by the console (or the type page above it) so the page header can open the
 * manual-usage form in one click and a successful log can close it. */
export function ServiceConsoleSections({ queue, manualForm, manualRows, reports, logging, onLogging }: {
  queue?: ReactNode; manualForm: ReactNode; manualRows: ReactNode; reports?: ReactNode; logging: boolean; onLogging: (open: boolean) => void;
}) {
  const [active, setActive] = useState(queue ? "queue" : "manual");
  const tabs = [...(queue ? [{ key: "queue", label: t`Queue`, href: "#" }] : []),
    { key: "manual", label: t`Manual usage`, href: "#" }, ...(reports ? [{ key: "reports", label: t`Printer reports`, href: "#" }] : [])];
  return <div className="grid gap-6">
    <Tabs tabs={tabs} activeKey={active} onChange={setActive} label={t`Service sections`}>
    {active === "queue" ? queue : null}
    {active === "manual" ? <><div className="flex justify-end"><button className="desk-button-primary" onClick={() => onLogging(true)}>{t`Log usage`}</button></div>
      {manualRows}</> : null}
    {active === "reports" ? reports : null}
  </Tabs>
    {logging ? <Modal open title={t`Log usage`} onClose={() => onLogging(false)}>{manualForm}</Modal> : null}
  </div>;
}
