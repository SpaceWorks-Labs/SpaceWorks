import type { Question } from "./types";

export function QuestionInput({ question: q, value, onChange, invalid, describedBy }: {
  question: Question; value: unknown; onChange: (value: unknown) => void; invalid?: boolean; describedBy?: string;
}) {
  const props = { id: `question-${q.id}`, "aria-label": q.type === "emergency_contact" ? undefined : q.label, "aria-invalid": invalid || undefined, "aria-describedby": describedBy,
    className: "desk-input w-full font-normal", required: q.required };
  const object = value && typeof value === "object" ? value as Record<string, unknown> : {};
  if (q.type === "emergency_contact") return <div className="grid gap-3 sm:grid-cols-3">{["name", "relationship", "phone"].map(key => <label key={key} className="grid gap-1 text-sm">{key === "name" ? "Contact name" : key === "phone" ? "Contact phone" : "Relationship"}<input {...props} required={key !== "relationship" && q.required} id={`${props.id}-${key}`} type={key === "phone" ? "tel" : "text"} maxLength={key === "phone" ? 32 : key === "relationship" ? 100 : 200} value={String(object[key] ?? "")} onChange={e => onChange({ name: "", relationship: "", phone: "", ...object, [key]: e.target.value })} /></label>)}</div>;
  if (q.type === "single_choice" || q.type === "multi_choice") {
    const selected = q.type === "single_choice" ? [object.option_id] : Array.isArray(object.option_ids) ? object.option_ids : [];
    const other = q.options?.find(option => option.other && selected.includes(option.id));
    return <div role="group" aria-label={q.label} aria-invalid={invalid || undefined} aria-describedby={describedBy} className="grid gap-2">{q.options?.map(option => <label key={option.id} className="flex min-h-11 items-center gap-3 font-normal"><input type={q.type === "single_choice" ? "radio" : "checkbox"} name={props.id} required={q.type === "single_choice" && q.required} checked={selected.includes(option.id)} onChange={e => q.type === "single_choice" ? onChange({ option_id: option.id }) : onChange({ ...object, option_ids: e.target.checked ? [...selected, option.id] : selected.filter(id => id !== option.id) })} />{option.label}</label>)}{other ? <label className="grid gap-1 text-sm">Describe your other choice<input {...props} id={`${props.id}-other`} required maxLength={q.bounds?.other_max_length ?? 300} value={String(object[q.type === "single_choice" ? "text" : "other_text"] ?? "")} onChange={e => onChange({ ...object, [q.type === "single_choice" ? "text" : "other_text"]: e.target.value })} /></label> : null}</div>;
  }
  if (q.type === "yes_no") return <select {...props} value={value === undefined ? "" : String(value)} onChange={e => onChange(e.target.value === "" ? undefined : e.target.value === "true")}><option value="">Choose an answer</option><option value="true">Yes</option><option value="false">No</option></select>;
  if (q.type === "long_text") return <textarea {...props} rows={4} placeholder={q.placeholder} minLength={q.bounds?.min_length} maxLength={q.bounds?.max_length} value={String(value ?? "")} onChange={e => onChange(e.target.value)} />;
  // Asset selection belongs to B/P's authorized upload flow; it is injected by the parent.
  if (q.type === "asset_reference") return <p className="text-sm text-muted">{object.asset_id ? "File selected" : "Choose a file using the upload control."}</p>;
  const type = ({ number: "number", date: "date", date_of_birth: "date", email: "email", phone: "tel", url: "url" } as Record<string, string>)[q.type] ?? "text";
  return <input {...props} type={type} placeholder={q.placeholder} min={q.bounds?.min} max={q.type === "date_of_birth" ? new Date().toISOString().slice(0, 10) : q.bounds?.max} minLength={q.bounds?.min_length} maxLength={q.bounds?.max_length} value={String(value ?? "")} onChange={e => onChange(q.type === "number" && e.target.value !== "" ? Number(e.target.value) : e.target.value)} />;
}
