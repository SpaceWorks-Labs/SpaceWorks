import { useQuery } from "@tanstack/react-query";

import { tenantPublicRequest } from "../../lib/api";
import type { JoinFieldModes, JoinFieldsInput, PublicAdmission } from "./membershipAdmissionApi";

// Mirrors `makerspaces/serializers_membership_l4.PublicPlanSerializer` and the invite check.
export type PublicPlan = {
  id: number; slug: string; name: string; description: string; plan_type: string; interval: string;
  custom_days: number | null; fixed_end_date: string | null; amount: string; renewal_price: string; currency: string;
  joining_fee: string | null; join_mode: "open" | "approval" | "invite_only" | "vouch" | "closed"; sort_order: number;
  /** X9: the plan's own application form (staff-only questions removed); null = the space form. */
  application_schema?: PublicAdmission["application_schema"] | null;
  /** Parity O-B2: photo / phone / state on this plan's join form. */
  join_fields?: JoinFieldModes;
};
export type InviteCheck = { valid: boolean; plan_id: number | null; plan_name: string; label: string };
export type JoinExtras = { plan_id?: number; invite_code?: string; /** Parity O-B1: the chosen unit's code. */ unit_code?: string;
  /** Parity O-B2: the join form's photo, phone and state. */ join_fields?: JoinFieldsInput };

/** Listed plans (X5/X8); a 404 means `membership.public_plans` is off, so there is no choice. */
export function usePublicPlans(slug: string) {
  return useQuery({ queryKey: ["public", slug, "membership-plans"], enabled: Boolean(slug), retry: false,
    queryFn: () => tenantPublicRequest<PublicPlan[]>(slug, `/public/${slug}/membership-plans`).catch(() => [] as PublicPlan[]) });
}

/** X11: whether a shared invite code still works. Checking never uses it up. */
export function useInviteLink(slug: string, code: string) {
  return useQuery({ queryKey: ["public", slug, "membership-invite", code], enabled: Boolean(slug && code), retry: false,
    queryFn: () => tenantPublicRequest<InviteCheck>(slug, `/public/${slug}/membership-invites/${encodeURIComponent(code)}`)
      .catch(() => ({ valid: false, plan_id: null, plan_name: "", label: "" })) });
}
