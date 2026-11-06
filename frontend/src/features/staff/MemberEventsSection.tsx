import { t } from "@lingui/core/macro";
import { StructuredApiError } from "../../lib/api";
import { EventHistoryLists } from "../events/EventHistoryLists";
import { useStaffMemberEventHistory } from "../events/eventHistoryApi";

/**
 * The member drawer's "Events" block. It needs manage_events or manage_members here; a viewer
 * without either gets a 403, and the block simply is not there for them.
 */
export function MemberEventsSection({ makerspaceId, userId }: { makerspaceId: number; userId: number }) {
  const history = useStaffMemberEventHistory(makerspaceId, userId);
  const status = history.error instanceof StructuredApiError ? history.error.status : undefined;
  if (status === 403) return null;
  return <section className="grid gap-3 border-t border-line pt-4" aria-labelledby={`member-events-${userId}`}>
    <h2 id={`member-events-${userId}`} className="title-panel">{t`Events`}</h2>
    {history.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading events…`}</p> : null}
    {status === 404 ? <p className="text-sm text-muted">{t`No events here yet.`}</p>
      : history.error ? <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-danger"><p>{t`Couldn't load events.`}</p>
        <button className="desk-button" type="button" onClick={() => { void history.refetch(); }}>{t`Retry`}</button></div> : null}
    {history.data ? <EventHistoryLists compact history={history.data} emptyMessage={t`No events here yet.`} /> : null}
  </section>;
}
