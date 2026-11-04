import { useState } from "react";
import { staffRequest } from "../../../lib/api";

type Reply = { answer: "yes" | "no" | null; note: string; replied_at: string | null; effect: string } | null;
type Row = { id: number; status: string; is_crew?: boolean; attendance_reply?: Reply };

/** Crew and "still coming?" chips for the guest list and the desk (lane L21a). */
export function ParticipationChips({ row }: { row: Row }) {
  const reply = row.attendance_reply;
  const label = !reply ? null : reply.answer === "yes" ? "Still coming" : reply.answer === "no" ? "Not coming" : "Asked, no answer";
  return <span className="mt-1 flex flex-wrap gap-1">
    {row.is_crew ? <span className="rounded-full border border-info px-2 py-0.5 text-xs font-semibold text-info-ink">Crew</span> : null}
    {label ? <span title={reply?.note || undefined}
      className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${reply?.answer === "no" ? "border-warn text-warn" : "border-line text-muted"}`}>
      {label}{reply?.note ? " · note" : ""}</span> : null}
  </span>;
}

/** Re-accept a declined registration (X42): the server checks capacity under the event lock. */
export function ReacceptButton({ eventId, row, onDone, onError }: {
  eventId: number; row: Row; onDone?: () => void; onError?: (error: Error) => void;
}) {
  const [pending, setPending] = useState(false), [due, setDue] = useState(false);
  if (row.status !== "rejected") return null;
  const reaccept = async () => {
    setPending(true);
    try {
      const result = await staffRequest<{ status: string; payment_due: boolean }>(
        `/admin/events/${eventId}/registrations/${row.id}/reaccept/`, { method: "POST", body: "{}" });
      setDue(result.payment_due);
      onDone?.();
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setPending(false);
    }
  };
  return <button className="desk-button-success" type="button" disabled={pending} onClick={() => void reaccept()}>
    {due ? "Re-accepted; payment due" : "Re-accept"}</button>;
}
