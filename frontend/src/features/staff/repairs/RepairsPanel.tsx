import { useSearchParams } from "react-router-dom";

import { SegmentedControl } from "../../../components/ui";
import { featureEnabled } from "../../../lib/features";
import type { Makerspace } from "../panels/shared";
import { TechniciansPanel } from "../technicians/TechniciansPanel";
import { IssueDetail } from "./IssueDetail";
import { IssueQueue } from "./IssueQueue";
import { MaintenanceView } from "./MaintenanceView";

const REPAIRS = ["machines.repairs", "inventory.repairs", "bookings.room_repairs"];
const UPKEEP = ["machines.maintenance", "inventory.maintenance", "bookings.room_maintenance"];

/**
 * The Repairs tab (#128 C-3/C-9). Managers (#102) get the queue, the technician directory and
 * item/room maintenance; a Technician gets "My jobs" and the maintenance due in their coverage.
 * The server decides every row and every step; this only picks which views to offer.
 */
export function RepairsPanel({ makerspace, actions }: { makerspace: Makerspace; actions: readonly string[] }) {
  const [params, setParams] = useSearchParams();
  const has = (action: string) => actions.includes(action);
  const manager = ["manage_machines", "edit_inventory", "manage_bookings", "manage_makerspace"].some(has);
  const features = makerspace.enabled_features ?? [];
  const repairsOn = REPAIRS.some(key => featureEnabled(features, key));
  const upkeepOn = UPKEEP.some(key => featureEnabled(features, key));
  const views = [
    ...(manager ? [{ value: "queue", label: "Queue" }] : []),
    ...(has("work_repairs") || manager ? [{ value: "mine", label: "My jobs" }] : []),
    ...(manager && repairsOn ? [{ value: "technicians", label: "Technicians" }] : []),
    ...(upkeepOn && (manager || has("run_maintenance")) ? [{ value: "upkeep", label: "Maintenance" }] : []),
  ];
  const view = views.find(row => row.value === params.get("rp_view"))?.value ?? views[0]?.value ?? "mine";
  const issueId = Number(params.get("issue")) || null;
  const set = (key: string, value: string | null) => setParams(current => {
    const next = new URLSearchParams(current);
    if (value === null) next.delete(key); else next.set(key, value);
    return next;
  });
  if (issueId) return <IssueDetail id={issueId} makerspaceId={makerspace.id} onBack={() => set("issue", null)} />;
  return <div className="grid gap-4">
    {views.length > 1 ? <SegmentedControl label="Repairs view" value={view} options={views} onChange={value => set("rp_view", value)} /> : null}
    {view === "queue" || view === "mine" ? <IssueQueue makerspace={makerspace} mine={view === "mine"} canOpen={manager && repairsOn}
      onOpen={id => set("issue", String(id))} /> : null}
    {view === "technicians" ? <TechniciansPanel makerspace={makerspace} canSetCoverage={has("manage_makerspace")} /> : null}
    {view === "upkeep" ? <MaintenanceView makerspace={makerspace} manager={manager} /> : null}
  </div>;
}
