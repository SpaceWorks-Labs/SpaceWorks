import { t } from "@lingui/core/macro";

import { featureEnabled } from "../../../lib/features";
import { GuestPassDesk } from "../../guestPasses/staff/GuestPassDesk";
import { MinorsDesk } from "./MinorsDesk";
import { VolunteerQueue } from "./VolunteerQueue";

type Tab = { key: string; label: string; href: string };

/**
 * Decision 223 sections of the Members tab: Guests, Minors and Volunteering. Each exists only while
 * the membership module and its capability are on (#95/#218: off = no UI). The server gate for all
 * three is manage_members, the same as the Members tab itself.
 */
export function communityMemberTabs(features: string[], membershipEnabled: boolean): Tab[] {
  if (!membershipEnabled) return [];
  const tabs: [string, string, string][] = [
    ["guests", t`Guests`, "membership.guest_passes"],
    ["minors", t`Minors`, "membership.minors"],
    ["volunteering", t`Volunteering`, "membership.volunteer_credit"],
  ];
  return tabs.filter(([, , key]) => featureEnabled(features, key)).map(([key, label]) => ({ key, label, href: `#${key}` }));
}

export function CommunityMemberTab({ tab, makerspaceId, features, canManageMakerspace }: {
  tab: string; makerspaceId: number; features: string[]; canManageMakerspace: boolean;
}) {
  if (tab === "guests") return <GuestPassDesk makerspaceId={makerspaceId} dayPassesOn={featureEnabled(features, "membership.day_passes")} />;
  if (tab === "minors") return <MinorsDesk makerspaceId={makerspaceId} canManageMakerspace={canManageMakerspace} />;
  if (tab === "volunteering") return <VolunteerQueue makerspaceId={makerspaceId} />;
  return null;
}
