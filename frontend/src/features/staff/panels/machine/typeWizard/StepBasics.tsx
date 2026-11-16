import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { staffRequest } from "../../../../../lib/api";
import { createMachineType, getMachineTypes, machineKeys, updateMachineType, collectionResults, type MachineType, type MeteringUnit } from "../../../machinesApi";
import type { JobSettings } from "../machineJobsApi";
import type { ApplyResult, TypeTemplate } from "./templatesApi";
import { useApplyTemplate } from "./templatesApi";

const METERING = (): [MeteringUnit, string][] => [["minutes", t`Minutes`], ["weight", t`Weight (grams)`], ["volume", t`Volume (millilitres)`], ["length", t`Length (millimetres)`], ["count", t`Count`]];
const slugify = (name: string) => name.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 50);

/** The job defaults a template carries are written through the existing job-settings endpoint; a refusal is reported, not fatal. */
export async function writeJobPrefill(makerspaceId: number, typeId: number, job: ApplyResult["prefill"]["job"]): Promise<string | null> {
  const body: Partial<JobSettings> = { accepts_job_requests: job.accepts_job_requests, runs_unattended: job.runs_unattended };
  try {
    await staffRequest(`/admin/makerspaces/${makerspaceId}/machine-types/${typeId}/job-settings`, { method: "PUT", body: JSON.stringify(body) });
    return null;
  } catch (error) { return error instanceof Error ? error.message : t`Job settings could not be saved.`; }
}

/** Step 2: name, icon, metering and visibility. For a new type this step creates it (from the template, or blank); for an existing type it saves the edit. */
export function StepBasics({ makerspaceId, machineType, template, machineServiceEnabled, publicMachines, onPublicChange, onSaved }: {
  makerspaceId: number; machineType: MachineType | null; template: TypeTemplate | null; machineServiceEnabled: boolean;
  publicMachines: boolean; onPublicChange: (value: boolean) => void; onSaved: (type: MachineType, apply: ApplyResult | null, warning: string | null) => void;
}) {
  const client = useQueryClient();
  const spec = template?.spec.basics;
  const config = machineType?.capability_config;
  const [name, setName] = useState(machineType?.name ?? template?.name ?? "");
  const [slug, setSlug] = useState(machineType?.slug ?? slugify(template?.name ?? ""));
  const [slugTouched, setSlugTouched] = useState(false);
  const [icon, setIcon] = useState(machineType?.icon ?? template?.icon ?? "");
  const [metering, setMetering] = useState<MeteringUnit>(config?.metering_unit ?? spec?.metering_unit ?? "minutes");
  const [booking, setBooking] = useState(config?.requires_booking ?? spec?.requires_booking ?? false);
  const apply = useApplyTemplate(makerspaceId);
  const locked = machineType?.is_builtin === true || machineType?.makerspace === null;
  const save = useMutation({ mutationFn: async () => {
    const capability_config = { ...(config ?? {}), metering_unit: metering, requires_booking: booking };
    if (machineType) return { type: await updateMachineType(makerspaceId, machineType.id, { name: name.trim(), icon: icon.trim(), capability_config }), result: null, warning: null };
    if (!template) return { type: await createMachineType(makerspaceId, { slug: slug.trim(), name: name.trim(), icon: icon.trim(), capability_config }), result: null, warning: null };
    const result = await apply.mutateAsync({ key: template.key, body: { name: name.trim(), slug: slug.trim() } });
    if (icon.trim() !== template.icon || metering !== template.spec.basics.metering_unit || booking !== template.spec.basics.requires_booking) {
      await updateMachineType(makerspaceId, result.machine_type_id, { name: name.trim(), icon: icon.trim(), capability_config });
    }
    const warning = machineServiceEnabled ? await writeJobPrefill(makerspaceId, result.machine_type_id, result.prefill.job) : null;
    await client.invalidateQueries({ queryKey: machineKeys.types(makerspaceId) });
    const type = collectionResults(await getMachineTypes(makerspaceId)).find(row => row.id === result.machine_type_id);
    if (!type) throw new Error(t`The type was created but could not be loaded. Close and reopen the wizard.`);
    return { type, result, warning };
  }, onSuccess: async ({ type, result, warning }) => { await client.invalidateQueries({ queryKey: machineKeys.types(makerspaceId) }); onSaved(type, result, warning); } });
  const ready = name.trim() && (machineType || slug.trim());
  return <form className="grid gap-3" onSubmit={event => { event.preventDefault(); if (ready) save.mutate(); }}>
    {locked ? <p className="text-sm text-muted">{t`This is a built-in type. Its structure is fixed; only pricing and the settings in later steps can change.`}</p> : null}
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Name`}<input className="desk-input" value={name} maxLength={100} required disabled={locked}
        onChange={event => { setName(event.target.value); if (!machineType && !slugTouched) setSlug(slugify(event.target.value)); }} /></label>
      <label className="grid gap-1 text-sm">{t`Slug`}<input className="desk-input code-text" value={slug} disabled={!!machineType} maxLength={50}
        onChange={event => { setSlugTouched(true); setSlug(event.target.value); }} />
        {machineType ? <span className="text-xs text-muted">{t`The slug is fixed once the type exists.`}</span> : null}</label>
      <label className="grid gap-1 text-sm">{t`Icon`}<input className="desk-input" value={icon} disabled={locked} placeholder={t`Optional icon`} onChange={event => setIcon(event.target.value)} /></label>
      <label className="grid gap-1 text-sm">{t`Metering unit`}<select className="desk-input" value={metering} disabled={locked} onChange={event => setMetering(event.target.value as MeteringUnit)}>
        {METERING().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    </div>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={booking} disabled={locked} onChange={event => setBooking(event.target.checked)} />{t`Machines of this type need a booking`}</label>
    <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={publicMachines} onChange={event => onPublicChange(event.target.checked)} />{t`Show new machines of this type on the public site`}</label>
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    <div><button type="submit" className="desk-button-primary min-h-11" disabled={!ready || save.isPending || locked && !!machineType}>
      {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : machineType ? t`Save basics` : t`Create type and continue`}</button></div>
  </form>;
}
