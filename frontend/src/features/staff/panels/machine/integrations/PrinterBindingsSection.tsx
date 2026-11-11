// Which enrolled printer device drives which machine of this type. A connected printer can be
// sent the in-progress job running on its machine, and reports the result back; staff apply a
// reported result (or let it apply itself). Needs devices + machines + machine_service.
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ConfirmDialog, ErrorBlock, StatusPill } from "../../../../../components/ui";
import { devicesApi } from "../../../devicesApi";
import { deviceQueryKeys } from "../../../deviceQueryKeys";
import type { Machine } from "../../../machinesApi";
import { useBindingMutation, usePrinterBindings, type PrinterBinding } from "./printerApi";
import { PrinterJobsList } from "./PrinterJobsList";

export function PrinterBindingsSection({ makerspaceId, machineTypeId, machines }: {
  makerspaceId: number; machineTypeId: number; machines: Machine[];
}) {
  const bindings = usePrinterBindings(makerspaceId);
  const devices = useQuery({ queryKey: deviceQueryKeys.list(makerspaceId, 1), queryFn: () => devicesApi.list(makerspaceId, 1) });
  const change = useBindingMutation(makerspaceId);
  const [removing, setRemoving] = useState<PrinterBinding | null>(null);
  const machineIds = new Set(machines.map(machine => machine.id));
  const rows = (bindings.data?.results ?? []).filter(row => row.machine !== null && machineIds.has(row.machine));
  const printers = (devices.data?.results ?? []).filter(device => device.kind === "printer" && device.status === "active");
  const deviceName = (id: string) => devices.data?.results.find(device => device.id === id)?.name ?? t`Unknown device`;
  const machineName = (id: number | null) => machines.find(machine => machine.id === id)?.name ?? t`Unknown machine`;
  return <section className="grid gap-3 rounded-xl border border-line bg-panel p-3" aria-label={t`Printer connections`}>
    <h3 className="title-panel">{t`Printer connections`}</h3>
    <p className="text-sm text-muted">{t`Connect an enrolled printer device to a machine of this type. Add and enrol devices in the Devices tab.`}</p>
    {bindings.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading printer connections…`}</p> : null}
    {bindings.error ? <ErrorBlock error={bindings.error} resource={t`printer connections`} onRetry={() => void bindings.refetch()} /> : null}
    {bindings.isSuccess && !rows.length ? <p className="text-sm text-muted">{t`No printer is connected to these machines yet.`}</p> : null}
    <ul className="grid gap-2" aria-label={t`Connected printers`}>
      {rows.map(row => <li key={row.id} className="flex flex-wrap items-center gap-3 rounded-control border border-line p-3">
        <span className="min-w-0 flex-1 text-sm"><strong className="block text-ink">{deviceName(row.device)}</strong>
          <span className="text-muted">{t`Drives ${machineName(row.machine)}`}</span></span>
        <StatusPill tone={row.enabled ? "success" : "neutral"} label={row.enabled ? t`On` : t`Off`} />
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5" checked={row.enabled}
          disabled={change.isPending} onChange={event => change.mutate({ id: row.id, patch: { enabled: event.target.checked } })} />{t`Connected`}</label>
        <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5" checked={row.auto_apply_terminal}
          disabled={change.isPending} onChange={event => change.mutate({ id: row.id, patch: { auto_apply_terminal: event.target.checked } })} />
          {t`Apply results automatically`}</label>
        <button type="button" className="desk-button-ghost min-h-11" onClick={() => setRemoving(row)}>{t`Disconnect`}</button>
      </li>)}
    </ul>
    <AddBinding makerspaceId={makerspaceId} machines={machines} printers={printers} />
    {change.error ? <ErrorBlock error={change.error} /> : null}
    {rows.length ? <PrinterJobsList makerspaceId={makerspaceId} machineTypeId={machineTypeId} machines={machines} bindings={rows} deviceName={deviceName} /> : null}
    <ConfirmDialog open={removing !== null} tone="danger" pending={change.isPending} title={t`Disconnect this printer?`}
      message={t`The device stays enrolled; it just stops driving this machine. Past printer jobs keep their records.`}
      confirmLabel={t`Disconnect`} onCancel={() => setRemoving(null)}
      onConfirm={() => { if (removing) change.mutate({ id: removing.id, remove: true }, { onSettled: () => setRemoving(null) }); }} />
  </section>;
}

function AddBinding({ makerspaceId, machines, printers }: {
  makerspaceId: number; machines: Machine[]; printers: { id: string; name: string }[];
}) {
  const change = useBindingMutation(makerspaceId);
  const [deviceId, setDeviceId] = useState("");
  const [machineId, setMachineId] = useState("");
  const [autoApply, setAutoApply] = useState(false);
  if (!printers.length) return <p className="text-sm text-muted">{t`No active printer device is enrolled. Enrol one in the Devices tab to connect it.`}</p>;
  return <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
    event.preventDefault();
    change.mutate({ create: { device_id: deviceId, machine_id: Number(machineId), enabled: true, auto_apply_terminal: autoApply } },
      { onSuccess: () => { setDeviceId(""); setMachineId(""); setAutoApply(false); } });
  }}>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Printer device`}</span>
      <select className="desk-input min-h-11" value={deviceId} onChange={event => setDeviceId(event.target.value)}>
        <option value="">{t`Choose a device…`}</option>
        {printers.map(device => <option key={device.id} value={device.id}>{device.name}</option>)}</select></label>
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Machine`}</span>
      <select className="desk-input min-h-11" value={machineId} onChange={event => setMachineId(event.target.value)}>
        <option value="">{t`Choose a machine…`}</option>
        {machines.map(machine => <option key={machine.id} value={machine.id}>{machine.name}</option>)}</select></label>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5" checked={autoApply}
      onChange={event => setAutoApply(event.target.checked)} />{t`Apply results automatically`}</label>
    <button type="submit" className="desk-button-primary min-h-11" disabled={!deviceId || !machineId || change.isPending}>
      {change.isPending ? t`Connecting…` : t`Connect printer`}</button>
    {change.error ? <div className="basis-full"><ErrorBlock error={change.error} /></div> : null}
  </form>;
}
