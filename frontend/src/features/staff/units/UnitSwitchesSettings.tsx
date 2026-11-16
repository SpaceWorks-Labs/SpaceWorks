import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ErrorText, SettingsRow } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";

export const UNITS_SWITCH = "membership.units";
export const UNIT_SCOPED_STAFF_SWITCH = "membership.unit_scoped_staff";

type Space = { id: number; enabled_features?: string[] };

/**
 * The two O-B1 switches, both off by default. Unit-scoped staff needs units, so it is offered only
 * while units are on, and turning units off also turns it off (the server lifts every narrowing).
 * Switching off hides every unit screen and keeps the data.
 */
export function UnitSwitchesSettings({ space }: { space: Space }) {
  const client = useQueryClient();
  const features = space.enabled_features ?? [];
  const unitsOn = features.includes(UNITS_SWITCH);
  const scopedOn = features.includes(UNIT_SCOPED_STAFF_SWITCH);
  const update = useMutation({
    mutationFn: (next: string[]) => staffRequest(`/admin/makerspaces/${space.id}`, { method: "PATCH", body: JSON.stringify({ enabled_features: next }) }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["makerspace-settings", space.id] });
      void client.invalidateQueries({ queryKey: ["makerspaces"] });
      void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
      void client.invalidateQueries({ queryKey: ["member-units", space.id] });
    },
  });
  const toggle = (key: string, on: boolean) => {
    const without = features.filter(feature => feature !== key && (key !== UNITS_SWITCH || on || feature !== UNIT_SCOPED_STAFF_SWITCH));
    update.mutate(on ? [...without, key] : without);
  };
  const box = (key: string, checked: boolean, label: string, disabled = false) => <label className="flex min-h-11 items-start gap-3 text-sm text-ink">
    <input type="checkbox" className="mt-0.5 h-5 w-5 accent-accent" checked={checked} disabled={disabled || update.isPending}
      onChange={event => toggle(key, event.target.checked)} /><span className="font-semibold">{label}</span></label>;
  return <>
    <SettingsRow label={t`Member units`} helper={t`Group members into areas, districts, chapters or branches inside this space, up to four named levels. Plans can be limited to units and each unit can have its own payment instructions.`}>
      {box(UNITS_SWITCH, unitsOn, t`Use member units`)}
    </SettingsRow>
    {unitsOn ? <SettingsRow label={t`Unit-scoped staff`} helper={t`Limit a staff member to the members of one unit and the units beneath it. Set the limit on each person under Staff & roles.`}>
      {box(UNIT_SCOPED_STAFF_SWITCH, scopedOn, t`Allow unit limits on staff`)}
    </SettingsRow> : null}
    {update.error ? <ErrorText message={update.error.message} /> : null}
  </>;
}
