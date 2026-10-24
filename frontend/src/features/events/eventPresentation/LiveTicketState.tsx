export function LiveTicketState({ status, attendedAt }: { status: string; attendedAt?: string | null }) {
  const attended = status === "attended";
  return <div className={`rounded-control border border-dashed p-3 ${attended ? "border-success-ink bg-success-soft text-success-ink" : "border-line text-muted"}`}
    role="status" aria-live="polite" data-ticket-state={attended ? "torn" : "intact"}>
    <p className="text-sm font-semibold">{attended ? "Checked in" : "Ready for event check-in"}</p>
    {attended && attendedAt ? <time className="text-sm" dateTime={attendedAt}>{new Date(attendedAt).toLocaleString()}</time> : null}
    <p className="text-xs">{attended ? "Your badge can still identify you at this event. Attendance is already recorded." : "The desk confirms attendance after scanning. This ticket refreshes automatically."}</p>
  </div>;
}
