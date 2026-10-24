import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { ErrorBlock } from "../../../components/ui";
import { CommandSession } from "../../events/hackathonAdmission/transport";
import { sessionScope } from "./sessionScope";

type Team = { id: number; name: string; state: string; version: number; member_count: number; eligibility_issue: boolean };
type Project = { id: number; team_name: string; title: string; state: string; version: number; triage: string; allowed_actions: string[]; assets: { id: number; state: string; kind: string; bytes: number }[] };
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export function ProgrammeTeamsPanel({ eventId, canTriage }: { eventId: number; canTriage: boolean }) {
  const [teamPage, setTeamPage] = useState(1), [projectPage, setProjectPage] = useState(1);
  const teams = useQuery({ queryKey: ["programme-teams", eventId, teamPage, ...sessionScope()], gcTime: 0,
    queryFn: () => staffRequest<Page<Team>>(`/admin/events/${eventId}/teams/?page=${teamPage}`) });
  const projects = useQuery({ queryKey: ["programme-projects", eventId, projectPage, ...sessionScope()], gcTime: 0,
    queryFn: () => staffRequest<Page<Project>>(`/admin/events/${eventId}/submissions/?page=${projectPage}`), enabled: canTriage });
  return <div className="grid gap-6"><section className="grid gap-3" aria-label="Programme teams"><h3 className="title-panel">Teams</h3>
    {teams.isPending ? <p role="status">Loading teams?</p> : null}{teams.error ? <ErrorBlock error={teams.error} /> : null}
    {teams.data?.results.map(row => <article key={row.id} className="rounded-control border border-line p-4"><h4 className="font-semibold">{row.name}</h4><p>{row.state} ? {row.member_count} members ? revision {row.version}</p>{row.eligibility_issue ? <p className="text-warn-ink">Review this team's eligibility.</p> : null}</article>)}
    <Pager page={teamPage} data={teams.data} change={setTeamPage} />
  </section>{canTriage ? <section className="grid gap-3" aria-label="Programme projects"><h3 className="title-panel">Projects</h3>
    {projects.error ? <ErrorBlock error={projects.error} /> : null}{projects.isPending ? <p role="status">Loading projects?</p> : null}
    {projects.data?.results.map(row => <ProjectCard key={row.id} eventId={eventId} row={row} />)}
    <Pager page={projectPage} data={projects.data} change={setProjectPage} />
  </section> : null}</div>;
}
function Pager({ page, data, change }: { page: number; data?: { previous: string | null; next: string | null }; change: (page: number) => void }) {
  return <div className="flex gap-2"><button className="desk-button" disabled={!data?.previous} onClick={() => change(page-1)}>Previous</button><button className="desk-button" disabled={!data?.next} onClick={() => change(page+1)}>Next</button></div>;
}
function ProjectCard({ eventId, row }: { eventId: number; row: Project }) {
  const [reason, setReason] = useState(""); const [triage, setTriage] = useState(row.triage);
  const command = useRef(new CommandSession()); const client = useQueryClient();
  const save = useMutation({ mutationFn: () => command.current.send(`/api/v1/admin/events/${eventId}/submissions/${row.id}/triage/`, "POST", {
    expected_version: row.version, triage, reason,
  }, true), onSuccess: () => client.invalidateQueries({ queryKey: ["programme-projects", eventId] }) });
  return <article className="grid gap-3 rounded-control border border-line p-4"><h4 className="font-semibold">{row.title || "Untitled draft"} ? {row.team_name}</h4><p>{row.state} ? revision {row.version}</p>
    <ul>{row.assets.map(asset => <li key={asset.id}>{asset.kind}: {asset.state} ({asset.bytes} bytes)</li>)}</ul>
    {row.allowed_actions.includes("triage") ? <><label className="grid gap-1">Eligibility<select className="desk-input" value={triage} onChange={e => setTriage(e.target.value)}>{["pending", "eligible", "ineligible", "hidden"].map(value => <option key={value}>{value}</option>)}</select></label>
      <label className="grid gap-1">Reason<textarea className="desk-input" maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label><button className="desk-button" disabled={!reason.trim() || save.isPending} onClick={() => save.mutate()}>Save project review</button></> : null}
    {save.error ? <p role="alert" className="text-danger">{save.error.message}</p> : null}
  </article>;
}
