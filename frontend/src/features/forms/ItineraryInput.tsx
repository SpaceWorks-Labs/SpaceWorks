import type { CompoundInputProps } from "./types";

function localDateTime(value: unknown) {
  if (typeof value !== "string") return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
export function ItineraryInput({ question: q, value, onChange, invalid, describedBy }: CompoundInputProps) {
  const object = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const props = { className: "desk-input", "aria-invalid": invalid || undefined, "aria-describedby": describedBy };
  const update = (key: string, item: unknown) => onChange({ ...object, [key]: item });
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return <div className="grid gap-3 sm:grid-cols-2">
    <label className="grid gap-1 text-sm">Travel mode<select {...props} required={q.required} value={String(object.mode ?? "")} onChange={e => onChange(e.target.value ? { ...object, mode: e.target.value } : undefined)}>
      <option value="">Choose a mode</option>{q.itinerary?.modes.map(mode => <option key={mode} value={mode}>{mode}</option>)}
    </select></label>
    {(["origin", "destination"] as const).map(key => <label key={key} className="grid gap-1 text-sm">{key === "origin" ? "Origin" : "Destination"}<input {...props} type="text" maxLength={200} value={String(object[key] ?? "")} onChange={e => update(key, e.target.value || null)} /></label>)}
    {(["depart_at", "arrive_at"] as const).map(key => <label key={key} className="grid gap-1 text-sm">{key === "depart_at" ? "Departure" : "Arrival"} ({zone})<input {...props} type="datetime-local" value={localDateTime(object[key])} onChange={e => {
      const date = new Date(e.target.value);
      update(key, Number.isFinite(date.getTime()) ? date.toISOString() : null);
    }} /></label>)}
    <p className="text-xs text-muted sm:col-span-2">Times use your device’s timezone. Leave unknown journey details blank.</p>
  </div>;
}
