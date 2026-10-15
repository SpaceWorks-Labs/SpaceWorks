import { useState } from "react";
import type { BookableSpace, Booking } from "./bookingsApi";
import { useEditBooking } from "./bookingToolsApi";
import { CustomFormFields } from "../forms/CustomFormFields";
import { customAnswerErrors, validateCustomAnswers, type CustomAnswers } from "../forms/customFormTypes";
import { StructuredApiError } from "../../lib/api";

export function canMoveBooking(booking: Booking, cutoffHours = 0, now = Date.now()) {
  return ["pending", "confirmed"].includes(booking.status)
    && new Date(booking.starts_at).getTime() - cutoffHours * 3600000 > now;
}

export function BookingReservationEditor({ space, booking }: { space: BookableSpace; booking: Booking }) {
  const [open, setOpen] = useState<"details" | "time" | null>(null);
  const [note, setNote] = useState(booking.note);
  const questionIds = new Set(space.custom_form?.map((question) => question.id));
  const initialAnswers: CustomAnswers = Object.fromEntries(
    (booking.custom_answers?.answers ?? []).filter((answer) => questionIds.has(answer.id)).map((answer) => [answer.id, answer.value]),
  );
  const [draftAnswers, setAnswers] = useState<CustomAnswers>(initialAnswers);
  // Compare and submit only current questions, retaining drafts for questions still shown.
  const answers: CustomAnswers = Object.fromEntries(Object.entries(draftAnswers).filter(([id]) => questionIds.has(id)));
  const answersChanged = JSON.stringify(answers) !== JSON.stringify(initialAnswers);
  const noteChanged = note !== booking.note;
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const edit = useEditBooking(space.makerspace_id, space.id, booking.id);
  const changeMode = (mode: "details" | "time") => { setOpen(mode); setErrors({}); edit.reset(); };
  return <div className="mt-3 grid gap-2">
    <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" onClick={() => changeMode("details")}>Edit note and answers</button>
      {canMoveBooking(booking, space.cancellation_cutoff_hours) ? <button className="desk-button" type="button" onClick={() => changeMode("time")}>Edit booking time</button> : null}</div>
    {open ? <form noValidate={open === "details"} aria-label={open === "details" ? "Edit reservation details" : "Edit reservation time"} className="grid gap-3 rounded-lg border border-line p-3" onSubmit={(event) => {
      event.preventDefault();
      if (open === "details") {
        const nextErrors = answersChanged ? validateCustomAnswers(space.custom_form, answers) : {}; setErrors(nextErrors);
        if (Object.keys(nextErrors).length) return;
        if (!noteChanged && !answersChanged) return;
        edit.mutate({ kind: "details", ...(noteChanged ? { note } : {}), ...(answersChanged ? { custom_answers: answers } : {}) }, { onSuccess: () => setOpen(null) });
      } else {
        edit.mutate({ kind: "time", starts_at: new Date(start).toISOString(), ends_at: new Date(end).toISOString() }, { onSuccess: () => setOpen(null) });
      }
    }}>
      {open === "details" ? <><label className="grid gap-1 text-sm">Reservation note<textarea className="desk-input" maxLength={5000} value={note} disabled={edit.isPending} onChange={(event) => setNote(event.target.value)} /></label>
        <CustomFormFields schema={space.custom_form} answers={answers} onChange={setAnswers} disabled={edit.isPending} errors={{ ...errors, ...customAnswerErrors(edit.error instanceof StructuredApiError ? edit.error.body.custom_answers : undefined) }} /></> : <>
        <p className="text-xs text-muted">Current rules and both cancellation cutoffs apply. Status and the flat charge stay the same.</p>
        <label className="grid gap-1 text-sm">New start (your local time)<input className="desk-input" type="datetime-local" required disabled={edit.isPending} value={start} onChange={(event) => setStart(event.target.value)} /></label>
        <label className="grid gap-1 text-sm">New end (your local time)<input className="desk-input" type="datetime-local" required min={start} disabled={edit.isPending} value={end} onChange={(event) => setEnd(event.target.value)} /></label>
      </>}
      {edit.error ? <p role="alert" className="text-danger">{edit.error.message}</p> : null}
      <div className="flex gap-2"><button className="desk-button-primary" disabled={edit.isPending || (open === "details" && !noteChanged && !answersChanged)}>{edit.isPending ? "Saving..." : open === "details" ? "Save reservation details" : "Save booking time"}</button><button type="button" className="desk-button" disabled={edit.isPending} onClick={() => setOpen(null)}>Keep current booking</button></div>
    </form> : null}
  </div>;
}
