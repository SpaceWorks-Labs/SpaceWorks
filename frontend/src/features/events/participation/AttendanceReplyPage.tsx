import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import { Card, ErrorText } from "../../../components/ui";

type Own = { event_id: number; event_title: string; starts_at: string; registration_id: number;
  answer: "yes" | "no" | null; note: string; replied_at: string | null; effect: string; free_on_no: boolean };

const EFFECTS: Record<string, string> = {
  released: "Your place was released for someone on the waitlist.",
  due_case: "Your place was cancelled. Any refund the event's policy allows is reviewed by the organisers.",
  left_to_staff: "The organisers will look at your group booking.",
};

/** The private "Are you still coming?" page: only the registered person sees and answers it. */
export function AttendanceReplyPage() {
  const { eventId } = useParams();
  const url = `/events/${Number(eventId)}/attendance/`;
  const client = useQueryClient();
  const own = useQuery({ queryKey: ["member-attendance", eventId], retry: false, queryFn: () => memberRequest<Own>(url) });
  const [note, setNote] = useState("");
  const reply = useMutation({ mutationFn: (answer: "yes" | "no") => memberRequest<Own>(url, {
    method: "POST", body: JSON.stringify({ answer, note }) }),
  onSuccess: data => client.setQueryData(["member-attendance", eventId], data) });
  if (own.error) return <main className="mx-auto max-w-xl p-4"><ErrorText message="This page is not available." /></main>;
  if (!own.data) return <main className="mx-auto max-w-xl p-4"><p role="status">Loading…</p></main>;
  const data = own.data, settled = data.effect !== "none";
  return <main className="mx-auto grid max-w-xl gap-4 p-4">
    <h1 className="font-display text-2xl text-ink">Are you still coming?</h1>
    <p className="text-ink">{data.event_title}, {new Date(data.starts_at).toLocaleString()}</p>
    {reply.error ? <ErrorText message={reply.error.message} /> : null}
    {data.answer ? <p role="status" className="text-ink">You answered: {data.answer === "yes" ? "still coming" : "not coming"}.</p> : null}
    {settled ? <Card><p className="text-sm text-ink">{EFFECTS[data.effect]}</p></Card> : <Card><div className="grid gap-3">
      <label className="grid gap-1 text-sm text-ink">A note for the organisers (optional)
        <textarea className="desk-input min-h-20" maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label>
      {data.free_on_no ? <p className="text-sm text-muted">If you answer No, your place goes to someone else.</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" disabled={reply.isPending} onClick={() => reply.mutate("yes")}>Yes, I'm coming</button>
        <button type="button" className="desk-button" disabled={reply.isPending} onClick={() => reply.mutate("no")}>No, I can't come</button>
      </div>
    </div></Card>}
  </main>;
}
