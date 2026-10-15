import { useState, type ReactNode } from "react";
import { EmptyState, Modal, Tabs } from "../../../../components/ui";
import type { MachineServiceRequest } from "../../../../generated/api";

// "Active" (everything not yet finished) is the default so running and ready jobs are never hidden
// behind an empty Pending tab — the pre-revamp console listed every job at once.
const ACTIVE = new Set(["pending", "accepted", "in_progress", "completed"]);
const statuses = [
  { key: "active", label: "Active" }, { key: "pending", label: "Pending" }, { key: "accepted", label: "Accepted" },
  { key: "in_progress", label: "In progress" }, { key: "completed", label: "Ready" },
  { key: "collected", label: "Collected" }, { key: "failed", label: "Failed" }, { key: "rejected", label: "Rejected" },
  { key: "all", label: "All jobs" },
];
/** Status keys a `?job_status=` deep link may open (dashboard work queues link straight to one). */
export const serviceQueueStatusKeys = statuses.map(item => item.key);
const matches = (key: string, status: string) => key === "all" || (key === "active" ? ACTIVE.has(status) : status === key);
const emptyCopy: Record<string, string> = {
  active: "No jobs waiting or running. New requests land here.", all: "No jobs yet. New requests land here.",
};
export function ServiceQueueTabs({ rows, children, initialStatus = "active" }: {
  rows: MachineServiceRequest[] | undefined; children: (rows: MachineServiceRequest[] | undefined) => ReactNode; initialStatus?: string;
}) {
  const [status, setStatus] = useState(serviceQueueStatusKeys.includes(initialStatus) ? initialStatus : "active");
  const visible = rows?.filter(row => matches(status, row.status));
  return <div className="grid gap-4"><Tabs activeKey={status} label="Job status" onChange={setStatus}
    tabs={statuses.map(item => ({ ...item, href: "#", count: rows?.filter(row => matches(item.key, row.status)).length }))}>
    {visible?.length === 0 ? <EmptyState message={emptyCopy[status] ?? "No jobs in this state."} /> : children(visible)}
  </Tabs></div>;
}

/** `logging` is owned by the console (or the type page above it) so the page header can open the
 * manual-usage form in one click and a successful log can close it. */
export function ServiceConsoleSections({ queue, manualForm, manualRows, reports, logging, onLogging }: {
  queue?: ReactNode; manualForm: ReactNode; manualRows: ReactNode; reports?: ReactNode; logging: boolean; onLogging: (open: boolean) => void;
}) {
  const [active, setActive] = useState(queue ? "queue" : "manual");
  const tabs = [...(queue ? [{ key: "queue", label: "Queue", href: "#" }] : []),
    { key: "manual", label: "Manual usage", href: "#" }, ...(reports ? [{ key: "reports", label: "Printer reports", href: "#" }] : [])];
  return <div className="grid gap-6">
    <Tabs tabs={tabs} activeKey={active} onChange={setActive} label="Service sections">
    {active === "queue" ? queue : null}
    {active === "manual" ? <><div className="flex justify-end"><button className="desk-button-primary" onClick={() => onLogging(true)}>Log usage</button></div>
      {manualRows}</> : null}
    {active === "reports" ? reports : null}
  </Tabs>
    {logging ? <Modal open title="Log usage" onClose={() => onLogging(false)}>{manualForm}</Modal> : null}
  </div>;
}
