import { useState } from "react";
import { CustomFormBuilder } from "../forms/CustomFormBuilder";
import type { BookableSpace, BookableSpacePayload } from "./bookingsApi";

export function BookingDetailsEditor({ space, pending, onSubmit }: {
  space: BookableSpace; pending: boolean; onSubmit: (values: Partial<BookableSpacePayload>) => void;
}) {
  const [name, setName] = useState(space.name);
  const [description, setDescription] = useState(space.description);
  const [location, setLocation] = useState(space.location);
  const [capacity, setCapacity] = useState(space.capacity);
  const [kind, setKind] = useState(space.kind);
  const [form, setForm] = useState(space.custom_form);
  return <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); onSubmit({ name, description, location, capacity, kind, custom_form: form }); }}>
    <label className="grid gap-1 text-sm">Name<input className="desk-input" required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} /></label>
    <label className="grid gap-1 text-sm">Type<select className="desk-input" value={kind} onChange={(event) => setKind(event.target.value as BookableSpace["kind"])}>{["dev_room", "bench", "meeting", "other"].map((value) => <option key={value} value={value}>{value.replace(/_/g, " ")}</option>)}</select></label>
    <label className="grid gap-1 text-sm">Description<textarea className="desk-input" value={description} onChange={(event) => setDescription(event.target.value)} /></label>
    <label className="grid gap-1 text-sm">Location<input className="desk-input" maxLength={255} value={location} onChange={(event) => setLocation(event.target.value)} /></label>
    <label className="grid gap-1 text-sm">Capacity<input className="desk-input" type="number" min={0} value={capacity} onChange={(event) => setCapacity(Number(event.target.value))} /></label>
    <CustomFormBuilder value={form} onChange={setForm} disabled={pending || !space.is_active} />
    <button className="desk-button-primary justify-self-start" disabled={pending || !space.is_active}>{pending ? "Saving..." : "Save details"}</button>
  </form>;
}
