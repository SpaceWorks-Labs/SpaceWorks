import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import { Card, ErrorText, StatusBadge } from "../../../components/ui";

type Crew = { id: number; version: number; crew_role: string; state: string; show_publicly: boolean };
type State = { event_id: number; event_title: string; starts_at: string; open: boolean; approval_required: boolean; crew: Crew | null };

const LABELS: Record<string, string> = { applied: "Waiting for review", approved: "You are on the crew",
  declined: "Not this time", withdrawn: "You withdrew", removed: "Removed by the organisers" };

/** The crew sign-up link (#128 C-36). A crew place is free; dietary needs stay private (#28). */
export function CrewSignupPage() {
  const { eventId } = useParams();
  const url = `/events/${Number(eventId)}/crew-signup/`;
  const client = useQueryClient();
  const state = useQuery({ queryKey: ["member-crew", eventId], retry: false, queryFn: () => memberRequest<State>(url) });
  const [role, setRole] = useState(""), [dietary, setDietary] = useState(""), [notes, setNotes] = useState("");
  const [shown, setShown] = useState(false);
  const save = (data: State) => client.setQueryData(["member-crew", eventId], data);
  const signup = useMutation({ mutationFn: () => memberRequest<State>(url, { method: "POST",
    body: JSON.stringify({ crew_role: role, dietary, notes, show_publicly: shown }) }), onSuccess: save });
  const withdraw = useMutation({ mutationFn: () => memberRequest<State>(url + "withdraw/", { method: "POST", body: "{}" }), onSuccess: save });
  if (state.error) return <div className="mx-auto max-w-xl p-4"><ErrorText message="This crew sign-up is not open." /></div>;
  if (!state.data) return <div className="mx-auto max-w-xl p-4"><p role="status">Loading…</p></div>;
  const data = state.data, live = data.crew && ["applied", "approved"].includes(data.crew.state);
  return <div className="mx-auto grid max-w-xl gap-4 p-4">
    <h1 className="font-display text-2xl text-ink">Join the crew</h1>
    <p className="text-ink">{data.event_title}, {new Date(data.starts_at).toLocaleString()}</p>
    {signup.error || withdraw.error ? <ErrorText message={(signup.error ?? withdraw.error)!.message} /> : null}
    {data.crew ? <Card><div className="flex flex-wrap items-center justify-between gap-3">
      <StatusBadge status={data.crew.state} label={LABELS[data.crew.state] ?? data.crew.state} />
      {live ? <button type="button" className="desk-button" disabled={withdraw.isPending} onClick={() => withdraw.mutate()}>Withdraw</button> : null}
    </div></Card> : null}
    {!live && data.open ? <Card><form className="grid gap-3" onSubmit={event => { event.preventDefault(); signup.mutate(); }}>
      <label className="grid gap-1 text-sm text-ink">How would you like to help? (optional)
        <input className="desk-input" maxLength={60} value={role} onChange={e => setRole(e.target.value)} placeholder="Door, AV, catering" /></label>
      <label className="grid gap-1 text-sm text-ink">Dietary needs (only counted for catering, never shown with your name)
        <input className="desk-input" maxLength={300} value={dietary} onChange={e => setDietary(e.target.value)} /></label>
      <label className="grid gap-1 text-sm text-ink">Anything else the organisers should know
        <textarea className="desk-input min-h-20" maxLength={1000} value={notes} onChange={e => setNotes(e.target.value)} /></label>
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={shown}
        onChange={e => setShown(e.target.checked)} />Show me in the event's public crew section (needs a public profile)</label>
      <p className="text-sm text-muted">{data.approval_required ? "The organisers review each sign-up." : "You join straight away."} Your crew place is free.</p>
      <button type="submit" className="desk-button justify-self-start" disabled={signup.isPending}>Sign up</button>
    </form></Card> : null}
  </div>;
}
