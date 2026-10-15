import { DangerZone, SettingsRow, SettingsSection, SettingsActions, StatCard } from "../../../../components/ui";
import { PublicMachineDisclosure } from "./PublicMachineDisclosure";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  machineKeys,
  machineImageEndpoint,
  retireMachine,
  unretireMachine,
  updateMachine,
  type Machine,
  type MachineStatus,
} from "../../machinesApi";
import { useMachineStatus } from "./useMachineStatus";
import { ImageUploader } from "../../ImageUploader";
import { MachinePublicSettings } from "../MachinePublicSettings";

const MACHINE_STATUSES: MachineStatus[] = ["idle", "running", "reserved", "maintenance", "offline"];
type MachineForm = Pick<Machine, "name" | "location" | "notes" | "firmware_version" | "camera_feed_url">;

export function OverviewTab({ machine, makerspaceId, canManageMachines, canEdit, canOperate, canRetire, canUnretire, publicDetailsEnabled = false }: {
  publicDetailsEnabled?: boolean;
  machine: Machine;
  makerspaceId: number;
  canManageMachines: boolean;
  canEdit: boolean;
  canOperate: boolean;
  canRetire: boolean;
  canUnretire: boolean;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<MachineForm>({
    name: "", location: "", notes: "", firmware_version: "", camera_feed_url: "",
  });
  const [status, setStatus] = useState<MachineStatus>(machine.status);

  useEffect(() => {
    setForm({
      name: machine.name,
      location: machine.location,
      notes: machine.notes,
      firmware_version: machine.firmware_version,
      camera_feed_url: machine.camera_feed_url,
    });
    setStatus(machine.status);
  }, [machine]);

  const refreshMachine = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: machineKeys.detail(machine.id) }),
      queryClient.invalidateQueries({ queryKey: machineKeys.list(makerspaceId) }),
    ]);
  };
  const save = useMutation({
    mutationFn: () => updateMachine(machine.id, {
      name: form.name.trim(),
      location: form.location.trim(),
      notes: form.notes.trim(),
      firmware_version: form.firmware_version.trim(),
      camera_feed_url: form.camera_feed_url.trim(),
    }),
    onSuccess: refreshMachine,
  });
  const setStatusMutation = useMachineStatus(machine.id, makerspaceId, status);
  const lifecycle = useMutation({
    mutationFn: (action: "retire" | "unretire") =>
      action === "retire" ? retireMachine(machine.id) : unretireMachine(machine.id),
    onSuccess: refreshMachine,
  });
  const updateField = (field: keyof MachineForm, value: string) =>
    setForm((current) => ({ ...current, [field]: value }));
  const canChangeLifecycle = machine.is_active ? canRetire : canUnretire;

  return (
    <div className="grid gap-6">
      <StatCard label="Usage hours" value={machine.usage_hours} />
      {canEdit && publicDetailsEnabled ? <PublicMachineDisclosure id={machine.id} makerspaceId={makerspaceId} fields={machine.public_fields ?? []} /> : null}
      <SettingsSection title="Machine details">
        {canEdit ? <SettingsRow label="Machine photo"><ImageUploader endpoint={machineImageEndpoint(machine.id)} currentUrl={machine.image_url} label="Machine photo" onChanged={() => { void refreshMachine(); }} /></SettingsRow> : null}
        {([['name', 'Name'], ['location', 'Location'], ['firmware_version', 'Firmware version'], ['camera_feed_url', 'Camera feed URL']] as const).map(([key, label]) =>
          <SettingsRow key={key} label={label} htmlFor={`machine-${key}`}><input id={`machine-${key}`} className="desk-input w-full" type={key === 'camera_feed_url' ? 'url' : 'text'} value={form[key]} disabled={!canEdit} onChange={event => updateField(key, event.target.value)} /></SettingsRow>)}
        <SettingsRow label="Notes" htmlFor="machine-notes"><textarea id="machine-notes" className="desk-input min-h-24 w-full" value={form.notes} disabled={!canEdit} onChange={event => updateField('notes', event.target.value)} /></SettingsRow>
      </SettingsSection>
      {canEdit ? <SettingsActions onDiscard={() => setForm({ name: machine.name, location: machine.location, notes: machine.notes, firmware_version: machine.firmware_version, camera_feed_url: machine.camera_feed_url })}
        onSave={() => save.mutate()} pending={save.isPending} disabled={!form.name.trim()} /> : null}
      {save.error instanceof Error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
      <section className="border-t border-line pt-4">
        <h3 className="title-section mb-3">Status</h3>
        <div className="flex flex-col gap-2 sm:flex-row">
          <select className="desk-input flex-1" aria-label="Machine status" value={status} disabled={!canOperate}
            onChange={(event) => setStatus(event.target.value as MachineStatus)}>
            {MACHINE_STATUSES.map((value) => (
              <option key={value} value={value}>{value.replace("_", " ")}</option>
            ))}
          </select>
          <button className="desk-button-primary" type="button"
            disabled={!canOperate || setStatusMutation.isPending} onClick={() => setStatusMutation.mutate()}>
            {setStatusMutation.isPending ? "Setting..." : "Set status"}
          </button>

        </div>
        {setStatusMutation.error instanceof Error ? <p className="mt-2 text-sm text-danger">{setStatusMutation.error.message}</p> : null}
        {lifecycle.error instanceof Error ? <p className="mt-2 text-sm text-danger">{lifecycle.error.message}</p> : null}
      </section>
      {canManageMachines ? (
        <MachinePublicSettings machine={machine} makerspaceId={makerspaceId} />
      ) : null}
      {canChangeLifecycle ? <DangerZone title={machine.is_active ? "Retire machine" : "Reactivate machine"}
        consequence={machine.is_active ? "Takes this machine out of service and off the public page." : "Returns this machine to service."}
        action={{ label: machine.is_active ? "Retire" : "Reactivate", pending: lifecycle.isPending, onClick: () => lifecycle.mutate(machine.is_active ? "retire" : "unretire") }} /> : null}
    </div>
  );
}
