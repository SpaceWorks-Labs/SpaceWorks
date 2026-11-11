import { t } from "@lingui/core/macro";
import type { SettingsLayoutSection } from "../../../components/layouts";
import { capabilityOn } from "../../../lib/features";
import { DayPassProductsSettings } from "../../guestPasses/settings/DayPassProductsSettings";
import { GuestPassPolicySettings } from "../../guestPasses/settings/GuestPassPolicySettings";
import { CommunityPolicySettings } from "./CommunityPolicySettings";
import { GuestWaiverSettings } from "./GuestWaiverSettings";

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/**
 * Decision 223 settings subpages under Operations: Guest passes and Community. Both need the
 * Space Manager (manage_makerspace on the server) and exist only while their capabilities are on
 * (#183B: a section for a switched-off feature is absent, not empty). EV-25: the visitor waiver gate is
 * its own section, present whenever guests can be on site (guest passes or presence check-in), so it
 * can still be set while guest passes are off (decision 226(a), B12).
 */
export function communitySettingsSections(space: Space, canManageMakerspace: boolean): SettingsLayoutSection[] {
  if (!canManageMakerspace) return [];
  const on = (key: string) => capabilityOn(space, key);
  const flags = { minors: on("membership.minors"), volunteer: on("membership.volunteer_credit"), joinFunnel: on("membership.join_funnel") };
  const passesOn = on("membership.guest_passes");
  const presenceOn = (space.enabled_modules ?? []).includes("presence");
  return [
    ...(passesOn ? [{ id: "guest-passes", title: t`Guest passes`,
      description: t`How guests borrow, use machines and are sponsored, and the day passes on sale.`, rows: <>
        <GuestPassPolicySettings key={`policy-${space.id}`} makerspaceId={space.id} />
        {on("membership.day_passes") ? <div className="pt-4"><DayPassProductsSettings key={`day-${space.id}`} makerspaceId={space.id} /></div> : null}
      </> }] : []),
    ...(passesOn || presenceOn ? [{ id: "visitor-waiver", title: t`Visitor waiver`,
      description: t`Whether non-members accept the waiver before they check in.`,
      rows: <GuestWaiverSettings key={`waiver-${space.id}`} makerspaceId={space.id} passesOn={passesOn} /> }] : []),
    ...(flags.minors || flags.volunteer || flags.joinFunnel ? [{ id: "community", title: t`Community`,
      description: t`Minors and guardian consent, volunteer credit and the join follow-up.`,
      rows: <CommunityPolicySettings key={space.id} makerspaceId={space.id} flags={flags} /> }] : []),
  ];
}
