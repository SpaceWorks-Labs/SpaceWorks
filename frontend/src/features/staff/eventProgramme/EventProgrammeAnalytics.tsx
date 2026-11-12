import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { eventErrorText } from "../eventUi";
import { EventAnalyticsExtras } from "./EventAnalyticsExtras";
import { EventFunnel, type Funnel } from "./EventFunnel";
import { sessionScope, useClearDeniedQuery } from "./sessionScope";
export function EventProgrammeAnalytics({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const key = ["event-programme-funnel", makerspaceId, eventId, ...sessionScope()];
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<{ typed_rows: Funnel[] }>(`/admin/makerspace/${makerspaceId}/analytics/event-programme?subject_kind=event&subject_id=${eventId}`) });
  useClearDeniedQuery(query.error, key);
  if (query.isLoading) return <LogoLoader label={t`Loading participation funnel…`} />;
  if (query.error) return <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p>;
  return <div className="grid gap-4">
    {query.data?.typed_rows[0] ? <EventFunnel data={query.data.typed_rows[0]} /> : <p className="text-sm text-muted">{t`No participation data yet.`}</p>}
    <EventAnalyticsExtras makerspaceId={makerspaceId} eventId={eventId} />
  </div>;
}
