import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Modal } from "../../../components/ui";
import { uploadIssuePhoto } from "./repairsApi";

export type StepField = {
  name: string; label: string; kind: "text" | "textarea" | "number" | "date" | "datetime" | "select" | "photos" | "checkbox";
  required?: boolean; options?: { value: string; label: string }[]; hint?: string; initial?: string;
};

/**
 * One small form per repair step. Each step names its fields; the dialog collects them,
 * uploads photos to their staging presigns first, and hands a plain body to `onSubmit`.
 * It replaces a dozen near-identical modal forms with one tested shape.
 */
export function StepDialog({ title, submitLabel, fields, makerspaceId, pending, error, onSubmit, onClose, note }: {
  title: string; submitLabel: string; fields: StepField[]; makerspaceId: number; pending: boolean; error?: string;
  onSubmit: (body: Record<string, unknown>) => void; onClose: () => void; note?: string;
}) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map(field => [field.name, field.initial ?? (field.kind === "select" ? field.options?.[0]?.value ?? "" : "")])));
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState("");
  const missing = fields.some(field => field.required && field.kind !== "photos" && !String(values[field.name] ?? "").trim());
  const set = (name: string, value: string) => setValues(current => ({ ...current, [name]: value }));
  async function submit() {
    const body: Record<string, unknown> = {};
    for (const field of fields) {
      const value = values[field.name];
      if (field.kind === "photos") continue;
      if (field.kind === "checkbox") body[field.name] = value === "true";
      else if (field.kind === "number") body[field.name] = value === "" ? null : Number(value);
      else if (field.kind === "datetime") body[field.name] = value ? new Date(value).toISOString() : null;
      else if (field.kind === "date") body[field.name] = value || null;
      else body[field.name] = value.trim();
    }
    if (fields.some(field => field.kind === "photos")) {
      try {
        setUploading("Uploading photos…");
        body.photos = await Promise.all(files.map(file => uploadIssuePhoto(makerspaceId, file)));
      } catch (problem) {
        setUploading(problem instanceof Error ? problem.message : "A photo could not be uploaded.");
        return;
      }
      setUploading("");
    }
    onSubmit(body);
  }
  return <Modal open title={title} onClose={onClose}>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault(); if (!missing) void submit(); }}>
      {fields.map(field => <FieldInput key={field.name} field={field} value={values[field.name] ?? ""} set={set} onFiles={setFiles} />)}
      {note ? <p className="text-sm text-muted">{note}</p> : null}
      {uploading ? <p role="status" className="text-sm text-muted">{uploading}</p> : null}
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-3">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={missing || pending || !!uploading}>{pending ? t`Saving…` : submitLabel}</button>
      </div>
    </form>
  </Modal>;
}

function FieldInput({ field, value, set, onFiles }: { field: StepField; value: string; set: (name: string, value: string) => void;
  onFiles: (files: File[]) => void }) {
  const hint = field.hint ? <span className="text-sm font-normal normal-case tracking-normal text-muted">{field.hint}</span> : null;
  if (field.kind === "checkbox") return <label className="flex min-h-11 items-center gap-2 text-sm">
    <input type="checkbox" checked={value === "true"} onChange={event => set(field.name, String(event.target.checked))} />{field.label}</label>;
  if (field.kind === "photos") return <label className="eyebrow grid gap-1">{field.label}
    <input className="desk-input" type="file" accept="image/jpeg,image/png,image/webp" multiple
      onChange={event => onFiles(Array.from(event.target.files ?? []).slice(0, 6))} />{hint}</label>;
  if (field.kind === "select") return <label className="eyebrow grid gap-1">{field.label}
    <select className="desk-input" value={value} onChange={event => set(field.name, event.target.value)}>
      {field.options?.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select>{hint}</label>;
  if (field.kind === "textarea") return <label className="eyebrow grid gap-1">{field.label}
    <textarea className="desk-input min-h-24" value={value} onChange={event => set(field.name, event.target.value)} />{hint}</label>;
  const type = field.kind === "datetime" ? "datetime-local" : field.kind === "text" ? "text" : field.kind;
  return <label className="eyebrow grid gap-1">{field.label}
    <input className="desk-input w-full min-w-0" type={type} min={field.kind === "number" ? "0" : undefined}
      step={field.kind === "number" ? "0.01" : undefined} value={value} onChange={event => set(field.name, event.target.value)} />{hint}</label>;
}
