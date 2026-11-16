import { t } from "@lingui/core/macro";
import { useId, type ReactNode } from "react";
import { SettingsRow, SettingsSection } from "../../components/ui";
import type { BookableSpacePayload } from "./bookingsApi";

type Props = {
  values: BookableSpacePayload;
  set: <K extends keyof BookableSpacePayload>(key: K, value: BookableSpacePayload[K]) => void;
  machineTypes: { id: number; name: string }[];
  typesError?: string;
  pagination: ReactNode;
  changeAvailability: (checked: boolean) => void;
  /** Machine time booking: whether the "Machine time" kind is offered, and the machine picker to show for it. */
  machineTime?: { available: boolean; picker: (id: string) => ReactNode };
  /** #184: false while booking charges are off -- no price input, one muted line instead. */
  chargesOn?: boolean;
};
export function BookableSpaceFields({ values, set, machineTypes, typesError, pagination, changeAvailability, machineTime, chargesOn = true }: Props) {
  const id = useId();
  const machineKind = values.kind === "machine";
  const notificationsValue = values.requester_notifications_enabled === null ? "inherit" : values.requester_notifications_enabled ? "on" : "off";
  return <>
    <SettingsSection title={t`Space details`}>
      <SettingsRow label={t`Name`} htmlFor={id + "-name"}><input id={id + "-name"} className="desk-input w-full" required maxLength={200}
        value={values.name} onChange={event => set("name", event.target.value)} /></SettingsRow>
      <SettingsRow label={t`Space type`} htmlFor={id + "-kind"}><select id={id + "-kind"} className="desk-input w-full" required
        value={values.kind} onChange={event => set("kind", event.target.value as BookableSpacePayload["kind"])}>
        <option value="dev_room">{t`Development room`}</option><option value="bench">{t`Bench`}</option><option value="meeting">{t`Meeting room`}</option><option value="other">{t`Other`}</option>
        {machineTime?.available || machineKind ? <option value="machine">{t`Machine time`}</option> : null}
      </select></SettingsRow>
      {machineKind && machineTime ? <SettingsRow label={t`Machine`} htmlFor={id + "-booked-machine"} helper={t`Members book time on this machine. Its machine type, and that type's training rules, apply automatically.`}>
        {machineTime.picker(id + "-booked-machine")}
      </SettingsRow> : null}
      <SettingsRow label={t`Capacity`} htmlFor={id + "-capacity"} helper={t`Use 0 when no capacity is published.`}>
        <input id={id + "-capacity"} className="desk-input w-full" type="number" min={0} value={values.capacity} onChange={event => set("capacity", Number(event.target.value))} />
      </SettingsRow>
      {machineKind ? null : <SettingsRow label={t`Machine type this room is for`} htmlFor={id + "-machine"} helper={t`Members need machine access for this type to book it.`}>
        <select id={id + "-machine"} className="desk-input w-full" value={values.machine_type ?? ""} onChange={event => set("machine_type", event.target.value ? Number(event.target.value) : null)}>
          <option value="">{t`No machine type`}</option>
          {values.machine_type && !machineTypes.some(type => type.id === values.machine_type) ? <option value={values.machine_type}>{t`Linked machine type #${values.machine_type}`}</option> : null}
          {machineTypes.map(type => <option key={type.id} value={type.id}>{type.name}</option>)}
        </select>{typesError ? <p className="mt-2 text-sm text-muted">{t`Machine type choices are unavailable: ${typesError}`}</p> : null}{pagination}
      </SettingsRow>}
      <SettingsRow label={t`Location`} htmlFor={id + "-location"}><input id={id + "-location"} className="desk-input w-full" maxLength={255}
        value={values.location} onChange={event => set("location", event.target.value)} /></SettingsRow>
      <SettingsRow label={t`Description`} htmlFor={id + "-description"}><textarea id={id + "-description"} className="desk-input min-h-24 w-full"
        value={values.description} onChange={event => set("description", event.target.value)} /></SettingsRow>
    </SettingsSection>
    <SettingsSection title={t`Booking and visibility`} description={t`Space Managers set approval mode, duration limits, buffers and cancellation policy in makerspace booking rules.`}>
      {chargesOn ? <SettingsRow label={t`Booking price`} htmlFor={id + "-price"} helper={t`Use 0 for no charge.`}><input id={id + "-price"} className="desk-input w-full" type="number" min="0" step="any"
        value={values.payment_amount} onChange={event => set("payment_amount", event.target.value)} /></SettingsRow>
        : <p className="text-sm text-muted">{t`Booking charges are off in this space, so bookings are free.`}</p>}
      <SettingsRow label={t`Requester email`} htmlFor={id + "-email"}><select id={id + "-email"} className="desk-input w-full" value={notificationsValue}
        onChange={event => set("requester_notifications_enabled", event.target.value === "inherit" ? null : event.target.value === "on")}>
        <option value="inherit">{t`Inherit makerspace setting`}</option><option value="on">{t`On`}</option><option value="off">{t`Off`}</option>
      </select></SettingsRow>
      <SettingsRow label={t`Public listing`}><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={values.is_public}
        onChange={event => set("is_public", event.target.checked)} />{t`Show this space on the public Bookings page`}</label></SettingsRow>
      <SettingsRow label={t`Published availability`}><label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={values.show_public_availability}
        onChange={event => changeAvailability(event.target.checked)} />{t`Publish confirmed booking intervals`}</label></SettingsRow>
      <SettingsRow label={t`Booker names`} helper={t`Names can appear only when booking intervals are published.`}>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={values.show_public_booker_names} disabled={!values.show_public_availability}
          onChange={event => set("show_public_booker_names", event.target.checked)} />{t`Show booker names with published intervals`}</label>
      </SettingsRow>
    </SettingsSection>
  </>;
}
