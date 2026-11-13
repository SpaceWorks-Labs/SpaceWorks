import { t } from "@lingui/core/macro";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { ErrorBlock } from "../../../components/ui";
import { CommandSession } from "../../events/hackathonAdmission/transport";
import { RotateCcw } from "lucide-react";
import { sessionScope } from "./sessionScope";
import { EventPanelPager } from "../EventPanelPager";
import { OrganiserTeamCard } from "./OrganiserTeamCard";
import { assetStateLabel, submissionStateLabel, triageLabel } from "./submissionLabels";
import type { OrganiserTeam } from "./organiserTeamApi";
import { ReinstateDialog } from "../hackathonJudging/ReinstateDialog";
import { LogoLoader } from "../../../components/LogoLoader";

type Project = { id: number; team_name: string; title: string; state: string; version: number; triage: string; allowed_actions: string[]; assets: { id: number; state: string; kind: string; bytes: number }[] };
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
/** `moderation`: `events.team_moderation` is on and the viewer may manage teams (C6 rename, move, delete with undo). */
export function ProgrammeTeamsPanel({ eventId, canTriage, moderation = false }: { eventId: number; canTriage: boolean; moderation?: boolean }) {
  const [teamPage, setTeamPage] = useState(1), [projectPage, setProjectPage] = useState(1);
  const [reinstating, setReinstating] = useState<Project | null>(null);
  const teams = useQuery({ queryKey: ["programme-teams", eventId, teamPage, ...sessionScope()], gcTime: 0,
    queryFn: () => staffRequest<Page<OrganiserTeam>>(`/admin/events/${eventId}/teams/?page=${teamPage}`) });
  const projects = useQuery({ queryKey: ["programme-projects", eventId, projectPage, ...sessionScope()], gcTime: 0,
    queryFn: () => staffRequest<Page<Project>>(`/admin/events/${eventId}/submissions/?page=${projectPage}`), enabled: canTriage });
  return <div className="grid gap-6"><section className="grid gap-3" aria-label={t`Programme teams`}><h3 className="title-panel">{t`Teams`}</h3>
    {teams.isPending ? <LogoLoader label={t`Loading teams…`} size={48} className="min-h-16 py-3" /> : null}{teams.error ? <ErrorBlock error={teams.error} /> : null}
    {teams.data?.results.map(row => <OrganiserTeamCard key={row.id} eventId={eventId} team={row} teams={teams.data.results} moderation={moderation} />)}
    <Pager page={teamPage} data={teams.data} change={setTeamPage} />
  </section>{canTriage ? <section className="grid gap-3" aria-label={t`Programme projects`}><h3 className="title-panel">{t`Projects`}</h3>
    {projects.error ? <ErrorBlock error={projects.error} /> : null}{projects.isPending ? <LogoLoader label={t`Loading projects…`} size={48} className="min-h-16 py-3" /> : null}
    {projects.data?.results.map(row => <ProjectCard key={row.id} eventId={eventId} row={row} onReinstate={() => setReinstating(row)} />)}
    <ReinstateDialog eventId={eventId} project={reinstating && { id: reinstating.id, version: reinstating.version, title: reinstating.title || t`Untitled draft` }}
      onClose={() => setReinstating(null)} />
    <Pager page={projectPage} data={projects.data} change={setProjectPage} />
  </section> : null}</div>;
}
function Pager({ page, data, change }: { page: number; data?: { count: number; previous: string | null; next: string | null }; change: (page: number) => void }) {
  return <EventPanelPager page={page} setPage={change} count={data?.count} next={data?.next} />;
}
function ProjectCard({ eventId, row, onReinstate }: { eventId: number; row: Project; onReinstate: () => void }) {
  const [reason, setReason] = useState(""); const [triage, setTriage] = useState(row.triage);
  const command = useRef(new CommandSession()); const client = useQueryClient();
  const save = useMutation({ mutationFn: () => command.current.send(`/api/v1/admin/events/${eventId}/submissions/${row.id}/triage/`, "POST", {
    expected_version: row.version, triage, reason,
  }, true), onSuccess: () => client.invalidateQueries({ queryKey: ["programme-projects", eventId] }) });
  return <article className="grid gap-3 rounded-control border border-line p-4"><h4 className="font-semibold">{row.title || t`Untitled draft`} · {row.team_name}</h4><p>{t`${submissionStateLabel(row.state)} · revision ${row.version}`}</p>
    <ul>{row.assets.map(asset => <li key={asset.id}>{asset.kind}: {assetStateLabel(asset.state)} ({t`${asset.bytes} bytes`})</li>)}</ul>
    {row.allowed_actions.includes("triage") ? <><label className="grid gap-1">{t`Eligibility`}<select className="desk-input" value={triage} onChange={e => setTriage(e.target.value)}>{["pending", "eligible", "ineligible", "hidden"].map(value => <option key={value} value={value}>{triageLabel(value)}</option>)}</select></label>
      <label className="grid gap-1">{t`Reason`}<textarea className="desk-input" maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label><button className="desk-button" disabled={!reason.trim() || save.isPending} onClick={() => save.mutate()}>{t`Save project review`}</button></> : null}
    {save.error ? <p role="alert" className="text-danger">{save.error.message}</p> : null}
    {row.triage === "ineligible" && row.state !== "withdrawn" ? <div className="flex flex-wrap items-center gap-3 border-t border-line pt-3">
      <p className="text-sm text-muted">{t`Disqualified. Reinstating restores its judging assignments and earlier scores.`}</p>
      <button type="button" className="desk-button inline-flex min-h-11 items-center gap-2" onClick={onReinstate}>
        <RotateCcw aria-hidden="true" className="size-4" />{t`Reinstate…`}</button></div> : null}
  </article>;
}
