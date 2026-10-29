import { SelectedReportPanel as Panel } from "./OperationsReportSelection";
import { DataState, PerMakerspaceTables, ReportTable, StatCards } from "./OperationsReportsParts";
import { OperationsReportsBookings } from "./OperationsReportsBookings";
import { OperationsReportsEvents } from "./OperationsReportsEvents";
import { OperationsReportsMachineUsage } from "./OperationsReportsMachineUsage";
import { OperationsReportsMaintenance } from "./OperationsReportsMaintenance";
import { type Makerspace } from "./shared";
import { capabilityOn } from "../../../lib/features";
import { useFablabReport, type FabLabHealthRow, type FablabPanelProps } from "./operationsReportsFablabApi";

export function OperationsReportsFablab({
  makerspace, aggregate, canViewAudit, startDate, endDate, makerspaceName,
}: {
  makerspace: Makerspace;
  aggregate: boolean;
  canViewAudit: boolean;
  startDate: string;
  endDate: string;
  makerspaceName: (id: number) => string;
}) {
  const modules = new Set(makerspace.enabled_modules ?? []);
  const reportsEnabled = aggregate || modules.has("reports");
  const base: FablabPanelProps = {
    makerspaceId: makerspace.id, aggregate, startDate, endDate, makerspaceName,
    enabled: canViewAudit && reportsEnabled,
  };
  const health = useFablabReport<FabLabHealthRow>("fablab-health", base);
  if (!canViewAudit) return null;

  const moduleEnabled = (module: string) => base.enabled && (aggregate || modules.has(module));
  const healthRow = health.data?.typed_rows[0];
  const healthStats: [string, number | undefined][] = [];
  if (healthRow?.events_available) healthStats.push(["Events in period", healthRow.events_in_period ?? 0], ["Registrations", healthRow.events_registrations ?? 0]);
  if (healthRow?.machines_available) healthStats.push(["Usage hours", Number(healthRow.machines_usage_hours ?? 0)]);
  if (healthRow?.maintenance_available) healthStats.push(["Maintenance logs", healthRow.maintenance_logs ?? 0], ["Overdue schedules (snapshot)", healthRow.maintenance_overdue_schedules ?? 0]);
  if (healthRow?.bookings_available) healthStats.push(["Upcoming bookings", healthRow.bookings_upcoming ?? 0]);
  return (
    <section className="contents" aria-label="FabLab analytics">
      <Panel title="FabLab health">
        {!reportsEnabled ? <p className="text-sm text-muted">Module disabled</p> : (
          <DataState loading={health.isLoading} error={health.error} onRetry={() => void health.refetch()} empty={!health.data?.typed_rows.length}>
            {aggregate ? (
              <PerMakerspaceTables data={health.data} nameOf={makerspaceName} />
            ) : healthRow ? (
              <>
                {healthStats.length ? <StatCards stats={healthStats} /> : null}
                <div className="mt-4 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
                  <HealthState label="Events" enabled={healthRow.events_enabled} available={healthRow.events_available} />
                  <HealthState label="Bookings" enabled={healthRow.bookings_enabled} available={healthRow.bookings_available} />
                  <HealthState label="Machines" enabled={healthRow.machines_enabled} available={healthRow.machines_available} />
                  <HealthState label="Maintenance" enabled={healthRow.maintenance_enabled} available={healthRow.maintenance_available} />
                </div>
                <ReportTable data={health.data} />
              </>
            ) : null}
          </DataState>
        )}
      </Panel>
      <OperationsReportsMachineUsage {...base} enabled={moduleEnabled("machines")} />
      <OperationsReportsEvents {...base} enabled={moduleEnabled("events")} />
      <OperationsReportsBookings {...base} enabled={moduleEnabled("bookings")} />
      <OperationsReportsMaintenance {...base} enabled={moduleEnabled("machines") && capabilityOn(makerspace, "machines.maintenance")} />
    </section>
  );
}

function HealthState({ label, enabled, available }: { label: string; enabled: boolean; available: boolean }) {
  const state = !enabled ? "Module disabled" : available ? "Available" : "Data unavailable";
  const tones: Record<string, string> = {
    Events: "border-accent bg-accent-soft",
    Bookings: "border-line bg-accent-soft",
    Machines: "border-success bg-success-soft",
    Maintenance: "border-warn bg-warn-soft",
  };
  return <div className={`rounded-md border px-3 py-2 ${tones[label] ?? "border-line bg-bg"}`}><span className="font-semibold text-ink">{label}</span><span className="ml-2 text-muted">{state}</span></div>;
}
