import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { EmptyState, ErrorText } from "../../components/ui";
import { getAccessToken, memberRequest, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { EventHistoryLists } from "./EventHistoryLists";
import { useMemberEventHistory } from "./eventHistoryApi";

/**
 * `member/events/history`: the events this account registered for or spoke at here. It sits
 * beside the ticket page rather than inside the membership dashboard, because an account-only
 * attendee — no membership, possibly no membership module — must be able to reach it too.
 */
export function MemberEventHistoryPage() {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const bootstrap = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const makerspaceId = tenant.mode === "single" ? tenant.makerspaceId : bootstrap.data?.makerspace.id;
  const space = tenant.mode === "single" ? tenant.bootstrap : bootstrap.data;
  const spaceName = space?.branding?.display_name || space?.makerspace.name || "Makerspace";
  const [restoring, setRestoring] = useState(!getAccessToken());
  useEffect(() => { if (restoring) refreshAccessToken().finally(() => setRestoring(false)); }, []);
  const identity = useQuery({ queryKey: ["member", "history-account"], queryFn: () => memberRequest<{ id: number }>("/auth/me"),
    enabled: !restoring, retry: false, staleTime: 0, gcTime: 0, refetchOnMount: "always" });
  const history = useMemberEventHistory(makerspaceId ?? undefined, identity.data?.id, !restoring && Boolean(identity.data?.id));
  const error = identity.error || history.error;
  const status = error instanceof StructuredApiError ? error.status : undefined;
  if (status === 401) return <MemberAuthPanel makerspaceSlug={makerspaceSlug}
    tenantBrand={space ? { name: spaceName, logo: space.branding?.logo_url || space.makerspace.logo_url || undefined } : undefined}
    onAuthenticated={() => { void identity.refetch(); }} />;
  return <CenteredCardLayout width="wide" eyebrow={spaceName} title="Your event history"
    state={restoring || identity.isLoading || history.isLoading || bootstrap.isLoading ? { status: "loading" } : { status: "ready" }}
    body="Events you registered for or spoke at in this space."
    content={<div className="grid gap-4">
      {/* 403: no registration or talk here yet, or this account can't see history in this space. */}
      {status === 403 ? <EmptyState message="No event history here yet. Events you register for or speak at will appear here." /> : null}
      {error && status !== 403 ? <ErrorText message={error.message} /> : null}
      {bootstrap.error ? <ErrorText message="Unable to load this makerspace." /> : null}
      {history.data ? <EventHistoryLists history={history.data} emptyMessage="No event history here yet. Events you register for or speak at will appear here." /> : null}
    </div>}
    primary={{ label: "See events", href: tenantPath("events") }} />;
}
