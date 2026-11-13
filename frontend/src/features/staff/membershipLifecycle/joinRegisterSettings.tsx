import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { SettingsLayoutSection } from "../../../components/layouts";
import { ErrorText, SettingsRow } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

// Parity O-B2 switches, all off by default (decision 218: off = the screens and routes are gone).
const SWITCHES = [
  { key: "membership.ask_changes", row: () => t`Ask applicants for changes`, label: () => t`Let reviewers send an application back`,
    helper: () => t`A reviewer adds a note; the applicant edits their answers and sends it back once. Turning this off never strands an application already sent back.` },
  { key: "membership.join_photo", row: () => t`Photo on the join form`, label: () => t`Plans may ask for a card photo`,
    helper: () => t`Each plan chooses off, optional or required. The photo goes on the member card only when the card has none.` },
  { key: "membership.join_contact_fields", row: () => t`Phone and state on the join form`, label: () => t`Plans may ask for a phone number and a state`,
    helper: () => t`Each plan chooses hidden, optional or required. The state is the GST place of supply on the member's invoices.` },
  { key: "membership.register_bulk", row: () => t`Bulk actions on the register`, label: () => t`Act on many members at once`,
    helper: () => t`Give a title, move to a unit, send a renewal reminder, or issue and email cards for up to 200 members, with a result for each.` },
];

/** Settings › People › Joining and the register: the four switches, each one row. */
export function JoinRegisterSwitches({ space }: { space: Space }) {
  const client = useQueryClient();
  const features = space.enabled_features ?? [];
  const update = useMutation({
    mutationFn: (next: string[]) => staffRequest(`/admin/makerspaces/${space.id}`, { method: "PATCH", body: JSON.stringify({ enabled_features: next }) }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["makerspace-settings", space.id] });
      void client.invalidateQueries({ queryKey: ["makerspaces"] });
      void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    },
  });
  const toggle = (key: string, on: boolean) => update.mutate(on ? [...features.filter((item) => item !== key), key] : features.filter((item) => item !== key));
  return <>
    {SWITCHES.map((item) => <SettingsRow key={item.key} label={item.row()} helper={item.helper()}>
      <label className="flex min-h-11 items-start gap-3 text-sm text-ink">
        <input type="checkbox" className="mt-0.5 h-5 w-5 accent-accent" checked={features.includes(item.key)} disabled={update.isPending}
          onChange={(event) => toggle(item.key, event.target.checked)} /><span className="font-semibold">{item.label()}</span></label>
      {item.key === "membership.register_bulk" && features.includes(item.key) && !features.includes("membership.register_tools")
        ? <p className="mt-1 text-sm text-warn-ink">{t`The register itself is off. Turn on "Register filters and export" under Features to use bulk actions.`}</p> : null}
    </SettingsRow>)}
    {update.error ? <ErrorText message={update.error.message} /> : null}
  </>;
}

export function joinRegisterSettingsSections(space: Space, canManageMakerspace: boolean): SettingsLayoutSection[] {
  if (!canManageMakerspace || !(space.enabled_modules ?? []).includes("membership")) return [];
  return [{ id: "joining", title: t`Joining and the register`,
    description: t`How applications are reviewed, what the join form asks, and bulk work on members.`,
    rows: <JoinRegisterSwitches key={space.id} space={space} /> }];
}
