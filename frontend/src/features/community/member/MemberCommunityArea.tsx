import { BringAGuest } from "../../guestPasses/member/BringAGuest";
import { DayPassShop } from "../../guestPasses/member/DayPassShop";
import { MyGuestPasses } from "../../guestPasses/member/MyGuestPasses";
import { GuardianConsentPanel } from "./GuardianConsentPanel";
import { OwnConsentStatusCard } from "./OwnConsentStatusCard";
import { JoinButton } from "./JoinButton";
import { VolunteerLog } from "./VolunteerLog";

/**
 * Decision 223 on the member Home tab: My passes (and day passes) for guests, Bring a guest for
 * members, guardian consent for guardians, the volunteer log for members. Each part is gated on
 * its capability here and again by the server (a switched-off feature answers 404 and the part
 * renders nothing).
 */
export function MemberCommunityArea({ makerspaceId, memberBase, features, activeMember }: {
  makerspaceId: number; memberBase: string; features: readonly string[]; activeMember: boolean;
}) {
  const on = (key: string) => features.includes(key);
  const paymentsHref = `${memberBase}/payments`;
  const join = on("membership.join_funnel") && !activeMember;
  return <>
    {on("membership.guest_passes") ? <MyGuestPasses makerspaceId={makerspaceId} paymentsHref={paymentsHref}
      joinSlot={join ? (passId) => <JoinButton makerspaceId={makerspaceId} source={{ guest_pass_id: passId }} memberHref={memberBase} /> : undefined} /> : null}
    {on("membership.guest_passes") && on("membership.day_passes") && !activeMember ? <DayPassShop makerspaceId={makerspaceId} paymentsHref={paymentsHref} /> : null}
    {on("membership.guest_passes") && activeMember ? <BringAGuest makerspaceId={makerspaceId} /> : null}
    {on("membership.minors") ? <OwnConsentStatusCard makerspaceId={makerspaceId} /> : null}
    {on("membership.minors") ? <GuardianConsentPanel makerspaceId={makerspaceId} /> : null}
    {on("membership.volunteer_credit") && activeMember ? <VolunteerLog makerspaceId={makerspaceId} /> : null}
  </>;
}
