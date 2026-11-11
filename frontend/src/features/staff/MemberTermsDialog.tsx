import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { EmptyState } from "../../components/ui/EmptyState";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, StatusPill } from "../../components/ui";
import { DetailLayout } from "../../components/layouts/DetailLayout";
import {
  cancelTerm,
  listPlans,
  listTerms,
  membershipPlanKeys,
  planErrorText,
  planIntervalLabel,
  startTerm,
} from "./membershipPlansApi";
import { useStaffChargesOn } from "./useStaffChargesOn";
import { formatMoney } from "./paymentsApi";
import { MemberLifecycleDetails } from "./membershipLifecycle/MemberLifecycleDetails";
import { StaffIncludedHours } from "./memberActivity/StaffIncludedHours";

/** Mount with `key={membershipId}`; the plan choice is per dialog, not per panel. */
export function MemberTermsDialog({
  makerspaceId,
  membershipId,
  memberName,
  onClose,
  features = [],
  userId,
}: {
  makerspaceId: number;
  membershipId: number;
  memberName: string;
  onClose: () => void;
  features?: string[];
  /** C26: the member's user id, for the included-hours line; omitted, the line is not shown. */
  userId?: number;
}) {
  const client = useQueryClient();
  const terms = useQuery({ queryKey: membershipPlanKeys.terms(membershipId), queryFn: () => listTerms(membershipId) });
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId) });
  const chargesOn = useStaffChargesOn("membership", makerspaceId); // #184: no prices while membership is free
  const activePlans = plans.data?.filter((plan) => plan.is_active) ?? [];
  const [planId, setPlanId] = useState<number | null>(null);
  const selectedPlan = planId ?? activePlans[0]?.id ?? null;
  const refresh = () => {
    client.invalidateQueries({ queryKey: membershipPlanKeys.terms(membershipId) });
    // Starting a term raises the plan's charge, so the roster's payment summary changes too.
    client.invalidateQueries({ queryKey: ["members", makerspaceId] });
    client.invalidateQueries({ queryKey: ["payments", makerspaceId] });
    // A new or cancelled term changes the included-hours pools.
    client.invalidateQueries({ queryKey: ["included-hours", makerspaceId] });
  };
  const start = useMutation({
    mutationFn: () => startTerm(membershipId, selectedPlan!),
    onSuccess: refresh,
  });
  const cancel = useMutation({ mutationFn: (termId: number) => cancelTerm(termId), onSuccess: refresh });
  const error = start.error ?? cancel.error;

  return (
    <DetailLayout presentation="drawer"
      open
      onClose={onClose}
      title={t`Membership terms for ${memberName}`}
      state={{ status: terms.isLoading ? "loading" : terms.isError ? "error" : "ready", error: t`Couldn't load terms. Try again.`, onRetry: () => { void terms.refetch(); } }}
      footer={{ secondary: [{ label: t`Close`, onClick: onClose }] }} main={<>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (selectedPlan) start.mutate();
        }}
      >
        <Field label={t`Plan`} className="min-w-48 flex-1">
          <select
            className="desk-input"
            value={selectedPlan ?? ""}
            disabled={!activePlans.length}
            onChange={(event) => setPlanId(Number(event.target.value))}
          >
            {!activePlans.length ? <option value="">{plans.isLoading ? t`Loading plans…` : t`No active plans`}</option> : null}
            {activePlans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name} · {planIntervalLabel(plan)}{chargesOn ? ` · ${formatMoney(plan.amount, plan.currency)}` : ""}
              </option>
            ))}
          </select>
        </Field>
        <button className="desk-button-primary" type="submit" disabled={!selectedPlan || start.isPending}>
          {start.isPending ? t`Starting…` : t`Start term`}
        </button>
      </form>
      {terms.isLoading ? <p className="mt-3 text-sm text-muted">{t`Loading terms…`}</p> : null}
      {terms.data?.length === 0 ? <EmptyState message={t`No terms yet.`} /> : null}
      {terms.data?.length ? (
        <ul className="mt-3 divide-y divide-line text-sm">
          {terms.data.map((term) => (
            <li key={term.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div>
                <p className="font-semibold text-ink">{term.plan_name}</p>
                <p className="text-xs text-muted">
                  {new Date(term.starts_at).toLocaleDateString(formatLocale())} – {term.is_lifetime ? "lifetime" : new Date(term.ends_at).toLocaleDateString(formatLocale())}
                  {term.kind ? ` · ${term.kind}` : ""}{chargesOn && term.price != null ? ` · ${formatMoney(term.price, term.currency || "usd")}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusPill tone={term.status === "active" ? "success" : term.status === "expired" ? "neutral" : "warn"} label={term.status} />
                {term.status === "active" ? (
                  <button className="desk-button" type="button" disabled={cancel.isPending} onClick={() => cancel.mutate(term.id)}>
                    {t`Cancel term`}</button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      {terms.isError ? <p className="mt-3 text-sm text-danger" role="alert">{planErrorText(terms.error, "Could not load terms.")}</p> : null}
      {error ? <p className="mt-3 text-sm text-danger" role="alert">{planErrorText(error, "Could not update the term.")}</p> : null}
      {userId ? <StaffIncludedHours className="mt-4" makerspaceId={makerspaceId} userId={userId} /> : null}
      <MemberLifecycleDetails membershipId={membershipId} makerspaceId={makerspaceId} features={features} />
    </>} />
  );
}
