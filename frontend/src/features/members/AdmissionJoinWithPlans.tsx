import type { ComponentProps } from "react";
import { useSearchParams } from "react-router-dom";

import { AdmissionJoin } from "./AdmissionJoin";
import { useInviteLink, usePublicPlans } from "./joinPlansApi";

/** Loads the listed plans and the page's `?invite=` link for the join form (X8, X11). */
export function AdmissionJoinWithPlans({ slug, ...props }: Omit<ComponentProps<typeof AdmissionJoin>, "plans" | "invite" | "inviteCode"> & { slug: string }) {
  const [search] = useSearchParams();
  const inviteCode = search.get("invite") ?? "";
  const plans = usePublicPlans(slug);
  const invite = useInviteLink(slug, inviteCode);
  return <AdmissionJoin {...props} plans={plans.data ?? []} invite={invite.data ?? null} inviteCode={inviteCode} />;
}
