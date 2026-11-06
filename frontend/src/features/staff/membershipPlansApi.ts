import { t } from "@lingui/core/macro";
import { StructuredApiError, staffRequest } from "../../lib/api";

// Hand-written mirrors of `apps/admin_api/serializers_membership_plans.py`. Regenerate
// `src/generated/api.ts` once the backend schema snapshot is refreshed and swap these out.
export type PlanInterval = "monthly" | "yearly" | "custom_days";
export type PlanType = "rolling" | "financial_year" | "fixed_end" | "lifetime";

export const PLAN_INTERVALS: [PlanInterval, string][] = [
  ["monthly", "Monthly"],
  ["yearly", "Yearly"],
  ["custom_days", "Custom number of days"],
];

export type MembershipPlan = {
  id: number;
  name: string;
  interval: PlanInterval;
  custom_days: number | null;
  amount: string;
  currency: string;
  is_active: boolean;
  auto_renew?: boolean;
  renewal_open_days?: number;
  renewal_grace_days?: number;
  renewal_retries?: number;
  reminder_days_before?: number[];
  reminder_days_after?: number[];
  // Release 2 (G16, X5, X6, X8, X9). Null overrides inherit the space default.
  plan_type?: PlanType;
  fixed_end_date?: string | null;
  renewal_amount?: string | null;
  renewal_price?: string;
  joining_fee?: string | null;
  rejoin_rule?: "never" | "once" | "each_join" | "after_lapse" | null;
  rejoin_after_days?: number | null;
  payment_timing?: "after_activation" | "before_activation" | null;
  join_mode?: "open" | "approval" | "invite_only" | "vouch" | "closed" | null;
  late_renewal?: "backdate" | "payment_day";
  slug?: string;
  description?: string;
  sort_order?: number;
  is_public?: boolean;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type MembershipPlanInput = Omit<MembershipPlan, "id" | "created_at" | "updated_at" | "renewal_price" | "archived_at">;

export type MembershipTerm = {
  id: number;
  membership: number;
  plan: number;
  plan_name: string;
  starts_at: string;
  ends_at: string;
  status: "active" | "expired" | "cancelled";
  renewal_payment: number | null;
  created_by: number | null;
  created_at: string;
  // Release 2 (X6, X7): what the term was sold for, its kind and derived standing.
  kind?: "new" | "renewal" | "reinstatement";
  price?: string | null;
  joining_fee?: string;
  currency?: string;
  plan_type?: PlanType;
  standing?: string;
  is_lifetime?: boolean;
};

export type InvitationRequest = {
  id: number;
  name: string;
  email: string;
  phone: string;
  message: string;
  status: "pending" | "invited" | "declined";
  handled_by: number | null;
  handled_at: string | null;
  created_at: string;
};

export const membershipPlanKeys = {
  plans: (makerspaceId: number) => ["membership-plans", makerspaceId] as const,
  terms: (membershipId: number) => ["membership-terms", membershipId] as const,
  invitationRequests: (makerspaceId: number) => ["invitation-requests", makerspaceId] as const,
};

export function listPlans(makerspaceId: number) {
  return staffRequest<MembershipPlan[]>(`/admin/makerspaces/${makerspaceId}/membership-plans`);
}

export function createPlan(makerspaceId: number, input: MembershipPlanInput) {
  return staffRequest<MembershipPlan>(`/admin/makerspaces/${makerspaceId}/membership-plans`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updatePlan(planId: number, input: Partial<MembershipPlanInput>) {
  return staffRequest<MembershipPlan>(`/admin/membership-plans/${planId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function setPlanArchived(planId: number, archived: boolean) {
  return staffRequest<MembershipPlan>(`/admin/membership-plans/${planId}/archive`, { method: archived ? "POST" : "DELETE" });
}

export function listTerms(membershipId: number) {
  return staffRequest<MembershipTerm[]>(`/admin/memberships/${membershipId}/terms`);
}

export function startTerm(membershipId: number, planId: number) {
  return staffRequest<MembershipTerm>(`/admin/memberships/${membershipId}/terms`, {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
  });
}

export function cancelTerm(termId: number) {
  return staffRequest<MembershipTerm>(`/admin/membership-terms/${termId}/cancel`, { method: "POST" });
}

export function listInvitationRequests(makerspaceId: number) {
  return staffRequest<InvitationRequest[]>(`/admin/makerspaces/${makerspaceId}/invitation-requests`);
}

export function inviteFromRequest(requestId: number, roleId: number) {
  return staffRequest<InvitationRequest>(`/admin/invitation-requests/${requestId}/invite`, {
    method: "POST",
    body: JSON.stringify({ role_id: roleId }),
  });
}

export function declineInvitationRequest(requestId: number) {
  return staffRequest<InvitationRequest>(`/admin/invitation-requests/${requestId}/decline`, {
    method: "POST",
  });
}

export function planIntervalLabel(plan: Pick<MembershipPlan, "interval" | "custom_days">) {
  if (plan.interval === "custom_days") return t`Every ${plan.custom_days ?? "?"} days`;
  return PLAN_INTERVALS.find(([value]) => value === plan.interval)?.[1] ?? plan.interval;
}

/** DRF field errors arrive as `{field: ["msg"]}`; flatten them so one line shows every problem. */
export function planErrorText(error: unknown, fallback: string) {
  if (error instanceof StructuredApiError) return error.message || fallback;
  return error instanceof Error ? error.message : fallback;
}
