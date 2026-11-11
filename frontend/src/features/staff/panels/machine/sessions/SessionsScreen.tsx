import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { ListLayout } from "../../../../../components/layouts";
import { useUrlListState } from "../../../../../lib/useUrlListState";
import { SavedViewsMenu } from "../../../SavedViewsMenu";
import { SessionFilters, SESSION_FILTERS, sessionFilterQuery } from "./SessionFilters";
import { Modal, PagePager } from "../../../../../components/ui";
import { fetchStaffSessions, sessionErrorMessage, sessionKeys, staffStartSession } from "../../../../machine-sessions/api";
import type { Machine } from "../../../machinesApi";
import { opsQueryState } from "../../../opsPresentation";
import { SessionMemberSelect } from "./SessionMemberSelect";
import { StaffSessionCard } from "./StaffSessionCard";

const FILTERS = [
  { key: "live", label: t`Live` },
  { key: "review", label: t`To check` },
  { key: "closed", label: t`Closed` },
];

/** Live and finished sessions for staff; `machineId` narrows it to one machine (the drawer tab). */
export function SessionList({ makerspaceId, machineId, status, extra = "" }: { makerspaceId: number; machineId?: number; status: string; extra?: string }) {
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ status, page: String(page), ...(machineId ? { machine: String(machineId) } : {}) });
  new URLSearchParams(extra).forEach((value, key) => { if (!machineId || key !== "machine") params.set(key, value); });
  const filters = params.toString();
  const sessions = useQuery({ queryKey: sessionKeys.staff(makerspaceId, filters), queryFn: () => fetchStaffSessions(makerspaceId, filters),
    refetchInterval: status === "live" ? 60_000 : false });
  const rows = sessions.data?.results ?? [];
  return <div className="grid gap-3">
    {sessions.isError ? <p role="alert" className="text-sm text-danger">{sessionErrorMessage(sessions.error)}</p> : null}
    {sessions.isSuccess && !rows.length && extra ? <p className="text-sm text-muted">{t`No sessions match these filters. Clear filters to see them all.`}</p> : null}
    {sessions.isSuccess && !rows.length && !extra ? <p className="text-sm text-muted">{status === "live" ? t`No one is using a machine right now.`
      : status === "review" ? t`Nothing to check. Auto-stopped and unattributed sessions show up here.` : t`No finished sessions yet.`}</p> : null}
    <ul className="grid gap-3">{rows.map(row => <StaffSessionCard key={row.id} session={row} makerspaceId={makerspaceId} />)}</ul>
    {sessions.data ? <PagePager page={page} setPage={setPage} next={sessions.data.next} /> : null}
  </div>;
}

function StartForMember({ makerspaceId, machines, onClose }: { makerspaceId: number; machines: Machine[]; onClose: () => void }) {
  const client = useQueryClient();
  const [machine, setMachine] = useState(machines[0]?.id ? String(machines[0].id) : "");
  const [member, setMember] = useState("");
  const start = useMutation({ mutationFn: () => staffStartSession(makerspaceId, Number(machine), Number(member)),
    onSuccess: () => { void client.invalidateQueries({ queryKey: sessionKeys.staffAll(makerspaceId) }); onClose(); } });
  return <Modal open onClose={onClose} title={t`Start a session for a member`}>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault(); start.mutate(); }}>
      <p className="text-sm text-muted">{t`The member must be checked in and certified, exactly as when they scan the machine themselves.`}</p>
      <label className="eyebrow grid gap-1">{t`Machine`}<select className="desk-input" required value={machine} onChange={event => { setMachine(event.target.value); setMember(""); }}>
          {machines.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
      <SessionMemberSelect machineId={Number(machine)} value={member} onChange={setMember} />
      {start.isError ? <p role="alert" className="text-sm text-danger">{sessionErrorMessage(start.error)}</p> : null}
      <button className="desk-button-primary justify-self-start" disabled={start.isPending || !machine || !member}>
        {start.isPending ? t`Starting…` : t`Start session`}</button>
    </form>
  </Modal>;
}

/** The Machines console Sessions screen (`?view=sessions`): live, to check, closed, with machine,
 * type, member, source and date filters (A16) that live in the URL and in saved views (A17). */
export function SessionsScreen({ makerspaceId, machines, onBack }: { makerspaceId: number; machines: Machine[]; onBack: () => void }) {
  const [params, setParams] = useSearchParams();
  const [starting, setStarting] = useState(false);
  const filter = FILTERS.find(row => row.key === params.get("session_status")) ?? FILTERS[0];
  const active = machines.filter(row => row.is_active);
  const list = useUrlListState(SESSION_FILTERS, "s_");
  const extra = sessionFilterQuery(list.values);
  return <>
    <ListLayout header={{ title: t`Machine sessions`, subtitle: t`Who is using which machine, and sessions that need a check.`,
      primary: active.length ? { label: t`Start for a member`, icon: "Plus", onClick: () => setStarting(true) } : undefined,
      secondary: { label: t`All machines`, onClick: onBack } }}
      tabs={FILTERS.map(row => ({ key: row.key, label: row.label, href: "#" }))} activeTab={filter.key}
      onTabChange={key => setParams(current => { const next = new URLSearchParams(current); next.set("session_status", key); return next; })}
      filters={{ activeCount: extra ? extra.split("&").length : 0, onClear: () => list.update({ ...SESSION_FILTERS }),
        views: <SavedViewsMenu makerspaceId={makerspaceId} entity="machine_sessions" state={list.values} onRestore={list.restore} />,
        controls: <SessionFilters machines={machines} values={list.values} onChange={patch => list.update(patch)} /> }}
      state={opsQueryState({ isLoading: false, error: null, refetch: () => undefined }, "sessions")} isEmpty={false}
      empty={{ message: t`No sessions.` }}
      body={{ kind: "rows", rows: <SessionList key={`${filter.key}?${extra}`} makerspaceId={makerspaceId} status={filter.key} extra={extra} /> }} />
    {starting ? <StartForMember makerspaceId={makerspaceId} machines={active} onClose={() => setStarting(false)} /> : null}
  </>;
}
