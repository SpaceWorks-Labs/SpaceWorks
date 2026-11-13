import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ListRow, Pagination, SegmentedControl, StatusPill } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { supervisedErrorMessage, useSupervisedSessions, type SessionFilter } from "./api";
import { LogoLoader } from "../../components/LogoLoader";

/** The sessions this person leads (a machine manager sees every session on machines they manage).
 *  `machineId` narrows the list to one machine on the server (`?machine=`). */
export function SupervisedSessionList({ makerspaceId, machineId, selectedId, onOpen }: {
  makerspaceId: number; machineId?: number; selectedId: number | null; onOpen: (id: number) => void;
}) {
  const [status, setStatus] = useState<SessionFilter>("open");
  const [page, setPage] = useState(1);
  const query = useSupervisedSessions(makerspaceId, status, page, machineId);
  const rows = query.data?.results ?? [];
  return <section aria-labelledby="supervised-list-title" className="grid min-w-0 gap-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 id="supervised-list-title" className="title-section">{t`Your supervised sessions`}</h3>
      <SegmentedControl label={t`Session status`} value={status} onChange={value => { setStatus(value as SessionFilter); setPage(1); }}
        options={[{ value: "open", label: t`Open` }, { value: "closed", label: t`Closed` }]} />
    </div>
    {query.isLoading ? <LogoLoader label={t`Loading sessions…`} size={48} className="min-h-16 py-3" />
      : query.error ? <div role="alert" className="grid justify-items-start gap-2 text-sm text-danger"><p>{supervisedErrorMessage(query.error)}</p>
        <button type="button" className="desk-button" onClick={() => void query.refetch()}>{t`Try again`}</button></div>
      : rows.length ? <div className="grid gap-3">{rows.map(row => {
        const people = row.participants.filter(person => !person.removed_at).length;
        return <ListRow key={row.id} title={row.machine_name} onClick={() => onOpen(row.id)}
          identity={{ kind: "icon", icon: "HardHat", tone: row.is_open ? "accent" : "neutral" }}
          meta={[t`Led by ${row.instructor_name}`, formatDateTime(row.opened_at), t`${people} supervised`].join(" · ")}
          right={selectedId === row.id ? <StatusPill tone="info" label={t`Showing`} />
            : <StatusPill tone={row.is_open ? "success" : "neutral"} label={row.is_open ? t`Open` : t`Closed`} />} />;
      })}</div>
      : <p className="text-sm text-muted">{status === "open" ? t`No open supervised sessions.` : t`No closed supervised sessions yet.`}</p>}
    {query.data && query.data.count > 24 ? <Pagination page={page} onChange={setPage} pageSize={24} count={query.data.count}
      totalPages={Math.ceil(query.data.count / 24)} /> : null}
  </section>;
}
