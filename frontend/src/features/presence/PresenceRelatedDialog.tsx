import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BoxSpinner } from "../../components/BoxSpinner";
import { Modal } from "../../components/ui";
import { formatDate } from "../../lib/format";
import { presenceApi, presenceKeys } from "./api";
import { clockTime, presenceErrorText } from "./presenceCopy";

const words = (value: string) => value.replace(/_/g, " ");

function Part({ title, children }: { title: string; children: ReactNode }) {
  return <section className="grid gap-1 rounded-lg border border-line p-3">
    <h3 className="text-sm font-semibold text-ink">{title}</h3>{children}</section>;
}

/** Read-only "Related" block for one live check-in: the event registration, the booking arrival and the
 * machine sessions around it. The server leaves out any part the viewer's area authority does not cover,
 * so an empty part reads the same whether it is absent or not theirs to see. */
export function PresenceRelatedDialog({ makerspaceId, accountId, name, onClose }: {
  makerspaceId: number; accountId: number; name: string; onClose: () => void;
}) {
  const related = useQuery({ queryKey: presenceKeys.related(makerspaceId, accountId), queryFn: () => presenceApi.related(makerspaceId, accountId) });
  const data = related.data;
  const empty = data && !data.event && !data.booking && !data.machine_sessions.length;
  return <Modal open onClose={onClose} title={t`Related to ${name}`} footer={<div className="flex justify-end">
    <button type="button" className="desk-button" onClick={onClose}>{t`Close`}</button></div>}>
    <div className="grid gap-3">
      <p className="text-sm text-muted">{t`What else this person is doing around this check-in. You only see the parts your role covers.`}</p>
      {related.isLoading ? <BoxSpinner label={t`Loading…`} /> : null}
      {related.isError ? <p role="alert" className="text-sm text-danger">{presenceErrorText(related.error).text}</p> : null}
      {data?.event ? <Part title={t`Event`}>
        <p className="text-sm">{data.event.title}</p>
        <p className="text-sm text-muted">{formatDate(data.event.starts_at)} · {clockTime(data.event.starts_at)}–{clockTime(data.event.ends_at)} · {words(data.event.registration_status)}</p>
      </Part> : null}
      {data?.booking ? <Part title={t`Booking`}>
        <p className="text-sm">{data.booking.space_name}</p>
        <p className="text-sm text-muted">{t`Arrived ${clockTime(data.booking.arrived_at)}`} · {clockTime(data.booking.starts_at)}–{clockTime(data.booking.ends_at)}</p>
      </Part> : null}
      {data?.machine_sessions.length ? <Part title={t`Machine sessions`}>
        <ul className="grid gap-1 text-sm">{data.machine_sessions.map((row) => <li key={row.session_id}>
          {row.machine_name} <span className="text-muted">· {clockTime(row.started_at)}–{row.ended_at ? clockTime(row.ended_at) : t`running now`}</span></li>)}</ul>
      </Part> : null}
      {empty ? <p className="text-sm text-muted">{t`Nothing else is linked to this check-in.`}</p> : null}
    </div>
  </Modal>;
}
