import { opsStatusLabel } from "./opsPresentation";
import { useEffect, useRef, useState } from "react";

import { ScanWorkbench } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { EventAttendanceTools } from "./EventAttendanceTools";
import {
  useMarkEventAttended,
  useResolveEventCheckIn,
  type EventCheckInResolution,
} from "./eventsApi";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

/** Staff-side QR check-in: scan, see who it is, then confirm.
 *
 * The two steps are deliberate and must not be collapsed into one. Resolving is read-only
 * and only reports a name; confirming is the mutation. Auto-confirming on scan would mean
 * a mis-aimed camera marks the wrong person present, and attendance is the record a paid
 * event is reconciled against.
 */
export default function EventCheckInScanner({
  makerspaceId,
  eventId,
  onClose,
}: {
  makerspaceId: number;
  eventId: number;
  onClose: () => void;
}) {
  const [resolved, setResolved] = useState<EventCheckInResolution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<string | null>(null);
  const [attendedId, setAttendedId] = useState<number | null>(null);
  const resolve = useResolveEventCheckIn(eventId);
  const attend = useMarkEventAttended(makerspaceId, eventId, "qr");
  // On a phone the workbench stacks the camera card and the code field ABOVE the result, so the
  // guest's name and the Confirm button land below the fold after every scan. Bring the result
  // panel into view whenever it changes; `nearest` leaves it alone when it is already visible.
  const sectionRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!resolved && !error && !confirmed) return;
    sectionRef.current?.querySelector<HTMLElement>("section[aria-labelledby]")?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [resolved, error, confirmed]);

  const handleScan = async (value: string) => {
    setError(null);
    setConfirmed(null);
    setAttendedId(null);
    setResolved(null);
    try {
      setResolved(await resolve.mutateAsync(value.trim()));
    } catch (cause) {
      // A 404 covers unknown, malformed and wrong-event tokens alike -- the endpoint
      // answers them identically on purpose -- so say the one thing that is true of all
      // three rather than surfacing a bare "not found".
      setError(
        cause instanceof StructuredApiError && cause.status === 404
          ? "That is not a check-in code for this event."
          : cause instanceof Error
            ? cause.message
            : "Could not read that code.",
      );
    }
  };

  const handleConfirm = async () => {
    if (!resolved) return;
    setError(null);
    try {
      await attend.mutateAsync(resolved.registration_id);
      setConfirmed(`${resolved.name} checked in.`);
      setAttendedId(resolved.registration_id);
      setResolved(null);
    } catch (cause) {
      if (cause instanceof StructuredApiError && cause.status === 409) {
        // A conflict is NOT proof of a duplicate check-in. `mark_attended` returns 409 for
        // every non-registered status, so between resolving and confirming another staffer
        // could have cancelled the registration or the whole event. Claiming "already
        // checked in" would then be a false statement made to someone standing at a door,
        // so say what is actually known and force a re-scan rather than leaving a stale
        // resolution with Confirm still enabled.
        setResolved(null);
        setError(
          `${resolved.name} could not be checked in -- the registration changed. Scan again to see its current state.`,
        );
        return;
      }
      setError(cause instanceof Error ? cause.message : "Could not confirm attendance.");
    }
  };

  // Gate on "registered" rather than excluding "waitlisted": `mark-attended` refuses every
  // other status, so an allow-list keeps a cancelled or already-attended code from offering
  // a button that can only fail. Excluding one status at a time is how the cancelled case
  // slipped through and reported a false "already checked in" to someone at the door.
  const confirmable = resolved?.status === "registered" && resolved.confirmable;
  const blockedReason = !resolved || confirmable
    ? null
    : resolved.status === "waitlisted"
      ? "Waitlisted registrations cannot be checked in until they are promoted."
      : resolved.status === "attended"
        ? "This registration is already checked in."
        : resolved.status === "cancelled"
          ? "This registration was cancelled, so it cannot be checked in."
          : resolved.event_status === "cancelled"
            ? "This event was cancelled, so attendance cannot be confirmed."
            : `Attendance cannot be confirmed while this event is ${resolved.event_status}.`;

  // Attendance tools (print the attended badge, correct a mistaken check-in) apply to the guest just
  // confirmed and to a scanned code that was already checked in. They carry the correction, so the
  // recent entry does not repeat it as a second, identical Undo.
  const toolsId = attendedId ?? (resolved?.status === "attended" ? resolved.registration_id : null);
  const attendanceTools = toolsId !== null ? <EventAttendanceTools eventId={eventId} makerspaceId={makerspaceId} registrationId={toolsId}
    onCorrected={() => { setAttendedId(null); setConfirmed(null); setResolved(null); }} /> : null;
  // `scroll-mb-*` keeps the scrolled-to result clear of the shell's bottom tabs and the home indicator.
  return <section ref={sectionRef} aria-labelledby="event-checkin-title" className="grid gap-4 [&_section[aria-labelledby]]:scroll-mb-[calc(var(--shell-bottom-tabs,0px)+env(safe-area-inset-bottom)+1rem)]">
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 id="event-checkin-title" className="title-panel">Check in by QR</h3><button className={`desk-button ${FOCUS}`} type="button" onClick={onClose}>Done</button></div>
    <ScanWorkbench onFind={handleScan} onScan={handleScan} searchLabel="Find a guest by check-in code" helper="Paste the guest’s event check-in code. Confirm their name before recording attendance."
      findPending={resolve.isPending || attend.isPending}
      result={resolved ? { title: resolved.name, tone: confirmable ? "success" : "warn", summary: <div className="grid gap-2"><p>{opsStatusLabel(resolved.status)}</p>{resolved.payment_status ? <p>Payment: {resolved.payment_status}</p> : null}{resolved.host_waiver_state === "missing" ? <p>No host waiver on file — take one at the desk.</p> : null}{blockedReason ? <p>{blockedReason}</p> : null}</div>,
        next: { label: "Confirm attendance", onClick: handleConfirm, disabled: !confirmable || attend.isPending, disabledReason: blockedReason || (attend.isPending ? "Attendance is being recorded." : undefined) },
      } : error ? { title: "Couldn’t check in", tone: "danger", summary: error, next: { label: "Scan another", onClick: () => { setError(null); setResolved(null); } } } : confirmed ? { title: confirmed, tone: "success", next: { label: "Scan another", onClick: () => { setConfirmed(null); setAttendedId(null); } } } : undefined}
      controls={resolved || attendanceTools ? <>{resolved ? <button className="desk-button" type="button" onClick={() => setResolved(null)}>Scan another</button> : null}{attendanceTools}</> : undefined}
      recent={confirmed ? [{ key: "latest", label: confirmed, tone: "success" }] : []} recentTitle="Recent check-ins" />
  </section>;
}
