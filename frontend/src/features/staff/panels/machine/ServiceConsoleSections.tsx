import { useState, type ReactNode } from "react";
import { EmptyState, Modal, Tabs } from "../../../../components/ui";
import type { MachineServiceRequest } from "../../../../generated/api";

const statuses = [
  { key: "all", label: "All jobs" },
  { key: "pending", label: "Pending" }, { key: "accepted", label: "Accepted" },
  { key: "in_progress", label: "Printing" }, { key: "completed", label: "Ready" },
  { key: "failed", label: "Failed" },
];
export function ServiceQueueTabs({ rows, children }: {
  rows: MachineServiceRequest[] | undefined; children: (rows: MachineServiceRequest[] | undefined) => ReactNode;
}) {
  const [status, setStatus] = useState("pending");
  const visible = rows?.filter(row => status === "all" || row.status === status);
  return <div className="grid gap-4"><Tabs activeKey={status} label="Job status" onChange={setStatus}
    tabs={statuses.map(item => ({ ...item, href: "#", count: rows?.filter(row => item.key === "all" || row.status === item.key).length }))}>
    {visible?.length === 0 ? <EmptyState message="No jobs waiting. New requests land here." /> : children(visible)}
  </Tabs></div>;
}

export function ServiceConsoleSections({ queue, manualForm, manualRows, reports }: { queue?: ReactNode; manualForm: ReactNode; manualRows: ReactNode; reports?: ReactNode }) {
  const [active, setActive] = useState(queue ? "queue" : "manual");
  const [logging, setLogging] = useState(false);
  const tabs = [...(queue ? [{ key: "queue", label: "Queue", href: "#" }] : []),
    { key: "manual", label: "Manual usage", href: "#" }, ...(reports ? [{ key: "reports", label: "Printer reports", href: "#" }] : [])];
  return <div className="grid gap-6">
    <Tabs tabs={tabs} activeKey={active} onChange={setActive} label="Service sections">
    {active === "queue" ? queue : null}
    {active === "manual" ? <><div className="flex justify-end"><button className="desk-button-primary" onClick={() => setLogging(true)}>Log usage</button></div>
      {manualRows}
      {logging ? <Modal open title="Log usage" onClose={() => setLogging(false)}>{manualForm}</Modal> : null}</> : null}
    {active === "reports" ? reports : null}
  </Tabs></div>;
}
