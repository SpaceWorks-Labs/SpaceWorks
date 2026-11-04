import { useCorrectAttendance } from "./eventFeedbackApi";
import { useGenerateEventBadges } from "./eventsBadgeApi";
import { eventErrorText } from "./eventUi";

export function EventAttendanceTools({ eventId, makerspaceId, registrationId, onCorrected }: {
  eventId: number; makerspaceId: number; registrationId: number; onCorrected: () => void;
}) {
  const correct = useCorrectAttendance(makerspaceId, eventId);
  const print = useGenerateEventBadges(eventId);
  return <div className="mt-3">
    <div className="flex flex-wrap gap-2">
      <button className="desk-button" type="button" disabled={print.isPending} onClick={() => print.mutate({
        registration_ids: [registrationId], include_attended: true,
      }, { onSuccess: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a"); link.href = url; link.download = "attendee-badge.pdf"; link.click();
        URL.revokeObjectURL(url);
      } })}>{print.isPending ? "Preparing badge…" : "Print attended badge"}</button>
      <button className="desk-button-danger-outline" type="button" disabled={correct.isPending} onClick={() => correct.mutate(registrationId, { onSuccess: onCorrected })}>Correct attendance</button>
    </div>
    {correct.error || print.error ? <p className="mt-2 text-sm text-danger" role="alert">{eventErrorText(correct.error || print.error)}</p> : null}
  </div>;
}
