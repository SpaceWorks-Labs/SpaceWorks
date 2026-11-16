import { useState, type ComponentProps } from "react";
import { useSearchParams } from "react-router-dom";

import { AdmissionJoin } from "./AdmissionJoin";
import { JoinUnitNotice } from "./JoinUnitNotice";
import { useInviteLink, usePublicPlans } from "./joinPlansApi";
import { usePublicUnits } from "./joinUnitsApi";

/** Loads the listed plans, the page's `?invite=` link and (parity O-B1) its `?unit=` unit for the join form (X8, X11). */
export function AdmissionJoinWithPlans({ slug, onJoin, ...props }: Omit<ComponentProps<typeof AdmissionJoin>, "plans" | "invite" | "inviteCode" | "unitSlot"> & { slug: string }) {
  const [search] = useSearchParams();
  const inviteCode = search.get("invite") ?? "";
  const linkCode = (search.get("unit") ?? "").trim().toUpperCase();
  const [unitCode, setUnitCode] = useState(linkCode);
  const plans = usePublicPlans(slug);
  const invite = useInviteLink(slug, inviteCode);
  const units = usePublicUnits(slug, unitCode);
  // A chosen unit narrows the plans to those offered in it (plan_ids is null without a resolved unit).
  const planIds = units.data?.selected?.code === unitCode ? units.data.plan_ids : null;
  const listed = (plans.data ?? []).filter(plan => !planIds || planIds.includes(plan.id));
  const chosenCode = units.data?.selected?.code === unitCode ? unitCode : "";
  return <AdmissionJoin {...props} plans={listed} invite={invite.data ?? null} inviteCode={inviteCode}
    onJoin={(answers, join) => onJoin(answers, { ...join, ...(chosenCode ? { unit_code: chosenCode } : {}) })}
    unitSlot={units.data ? <JoinUnitNotice data={units.data} code={unitCode} linkCode={linkCode}
      settling={units.isPlaceholderData || units.isFetching} onChange={setUnitCode} /> : null} />;
}
