import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { CenteredCardLayout } from "../../components/layouts";
import { ErrorBlock, Field, Pagination } from "../../components/ui";
import { getAccessToken, memberRequest, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { publicFamilies } from "../../lib/publicHome";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { personalRecipientKey } from "../notifications/personalQueryKeys";
import { HelpLink } from "../help/HelpLink";
import { MemberAuthPanel } from "./MemberAuthPanel";
import { BorrowingHistoryList } from "./BorrowingHistoryList";
import { MemberWaitlist } from "./MemberWaitlist";
import { useOwnBorrowingHistory, type BorrowingPeriod } from "./borrowingHistoryApi";
import { RouteLink } from "../../components/ui/RouteLink";

/** Account-only owner history, independent of the optional membership dashboard and payment rail. */
export function MemberBorrowingHistoryPage() {
  const { slug = "" } = useParams();
  const tenant = useTenant();
  const spaceSlug = tenant.mode === "single" ? tenant.slug : slug;
  const path = useTenantPath(spaceSlug);
  const bootstrapQuery = useTenantBootstrap(spaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const available = Boolean(bootstrap?.modules.includes("request_workflow") && bootstrap.features.includes("loans.enabled"));
  const inventoryPublished = Boolean(bootstrap && publicFamilies(bootstrap).includes("inventory"));
  const client = useQueryClient();
  const [restoring, setRestoring] = useState(!getAccessToken("person"));
  const [period, setPeriod] = useState<BorrowingPeriod>("all");
  const [page, setPage] = useState(1);
  useEffect(() => {
    let active = true;
    if (restoring) void refreshAccessToken("person").catch(() => null).finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, [restoring]);
  const identity = useQuery({ queryKey: ["member", "borrowing-account", personalRecipientKey()],
    queryFn: () => memberRequest<{ id: number }>("/auth/me"), enabled: !restoring && available,
    retry: false, staleTime: 0, gcTime: 0 });
  const history = useOwnBorrowingHistory(bootstrap?.makerspace.id, identity.data?.id, period, page,
    available && !restoring && Boolean(identity.data?.id));
  const error = identity.error || history.error || bootstrapQuery.error;
  if (error instanceof StructuredApiError && error.status === 401) return <MemberAuthPanel makerspaceSlug={spaceSlug}
    tenantBrand={bootstrap ? { name: bootstrap.branding.display_name || bootstrap.makerspace.name, logo: bootstrap.makerspace.logo_url || undefined } : undefined}
    onAuthenticated={() => { client.removeQueries({ queryKey: ["member", "borrowing-history"] }); void identity.refetch(); }} />;
  const busy = restoring || bootstrapQuery.isLoading || identity.isLoading || history.isLoading;
  const unavailable = Boolean(bootstrap && !available);
  return <CenteredCardLayout width="wide" eyebrow={bootstrap?.branding.display_name || bootstrap?.makerspace.name}
    title={t`Your borrowing history`} body={unavailable ? t`Borrowing history is unavailable for this space.` : t`Your requests, handovers and returns in this space.`}
    state={busy ? { status: "loading" } : { status: "ready" }}
    content={<div className="grid min-w-0 gap-5">
      {error ? <ErrorBlock error={error} onRetry={() => {
        if (bootstrapQuery.error) void bootstrapQuery.refetch();
        if (identity.error) void identity.refetch();
        if (history.error && available && identity.data?.id) void history.refetch();
      }} /> : null}
      {available && !error ? <>
        <Field label={t`Borrowing view`}><select className="desk-input w-full" value={period} onChange={event => { setPeriod(event.target.value as BorrowingPeriod); setPage(1); }}>
          <option value="all">{t`All borrowing`}</option><option value="current">{t`Requests and current loans`}</option><option value="history">{t`Closed requests and returns`}</option>
        </select></Field>
        {/* The only waitlist screen an account-only borrower has: the member area's Loans tab needs the membership module. */}
        {bootstrap?.features.includes("loans.waitlist") && identity.data?.id ? <MemberWaitlist makerspaceId={bootstrap.makerspace.id} makerspaceSlug={spaceSlug} /> : null}
        {history.data ? <><BorrowingHistoryList rows={history.data.results} space={bootstrap ? { makerspaceId: bootstrap.makerspace.id, makerspaceSlug: spaceSlug } : undefined}
          withdraw={bootstrap?.features.includes("loans.withdrawals") ? { makerspaceId: bootstrap.makerspace.id, makerspaceSlug: spaceSlug } : undefined} /><Pagination page={page} count={history.data.count} pageSize={24}
          totalPages={Math.max(1, Math.ceil(history.data.count / 24))} onChange={setPage} disabled={history.isFetching} /></> : null}
      </> : null}
      <nav aria-label={t`Related account history`} className="flex flex-wrap gap-3">
        <RouteLink className="desk-button" href={path("member/payments")}>{t`Payments & receipts`}</RouteLink>
        <RouteLink className="desk-button" href={path("member/account")}>{t`Your account`}</RouteLink>
      </nav>
      {bootstrap ? <HelpLink article="member/borrow-tools" makerspace={{ slug: spaceSlug, enabled_features: bootstrap.features }} singleTenant={tenant.mode === "single"} /> : null}
    </div>}
    primary={{ label: inventoryPublished ? t`Browse inventory` : t`Back to home`, href: path(inventoryPublished ? "inventory" : "") }} />;
}
