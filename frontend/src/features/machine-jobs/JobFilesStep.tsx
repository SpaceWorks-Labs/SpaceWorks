import type { ChangeEvent } from "react";

import { EmptyState, Field, ListRow } from "../../components/ui";
import { fileKey, type FileErrors } from "./jobUploads";

/** Client-side format check, so an obviously wrong file is flagged before anything is uploaded. */
export function formatError(file: File, accepted: string[]) {
  if (!accepted.length) return "";
  const name = file.name.toLowerCase();
  return accepted.some(ext => name.endsWith(ext)) ? "" : `This machine doesn't take ${name.includes(".") ? name.slice(name.lastIndexOf(".")) : "this kind of"} files.`;
}

function FileList({ label, files, errors, onRemove }: { label: string; files: File[]; errors: FileErrors; onRemove: (file: File) => void }) {
  if (!files.length) return null;
  return <ul className="grid gap-2" aria-label={`Chosen ${label.toLowerCase()}`}>{files.map(file => {
    const error = errors[fileKey(file)];
    return <li key={fileKey(file)}><ListRow title={file.name}
      meta={error ? <span className="text-danger">{error}</span> : `${Math.max(1, Math.round(file.size / 1024))} KB`}
      right={<button className="desk-button-ghost text-danger" type="button" aria-label={`Remove ${file.name}`} onClick={() => onRemove(file)}>Remove</button>} /></li>;
  })}</ul>;
}

/** Step 2: the design files (at least one) and optional screenshots, each with its own error. */
export function JobFilesStep({ accepted, models, screenshots, errors, onChange, typeName, disabled, optional = false }: {
  accepted: string[]; models: File[]; screenshots: File[]; errors: FileErrors; typeName: string; disabled?: boolean; optional?: boolean;
  onChange: (next: { models?: File[]; screenshots?: File[] }) => void;
}) {
  const add = (kind: "models" | "screenshots") => (event: ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(event.target.files ?? []);
    const current = kind === "models" ? models : screenshots;
    const known = new Set(current.map(fileKey));
    onChange({ [kind]: [...current, ...picked.filter(file => !known.has(fileKey(file)))] });
    event.target.value = "";
  };
  const allErrors = { ...errors };
  for (const file of models) if (!allErrors[fileKey(file)]) { const error = formatError(file, accepted); if (error) allErrors[fileKey(file)] = error; }
  return <fieldset className="grid gap-5" disabled={disabled}>
    <legend className="title-section mb-1">{optional ? "New files (optional)" : "Your files"}</legend>
    <div className="grid gap-3">
      <Field label="Design files" hint={accepted.length ? `${typeName} accepts ${accepted.join(", ")}.` : undefined}>
        <input className="desk-input w-full" type="file" multiple accept={accepted.join(",") || undefined} onChange={add("models")} />
      </Field>
      <FileList label="Design files" files={models} errors={allErrors} onRemove={file => onChange({ models: models.filter(row => row !== file) })} />
      {!models.length && !optional ? <EmptyState message="Add at least one design file. Screenshots alone can't be made." /> : null}
    </div>
    <div className="grid gap-3">
      <Field label="Screenshots (optional)" hint="For example your slicer's time estimate, or a picture of what you want.">
        <input className="desk-input w-full" type="file" multiple accept="image/*,application/pdf" onChange={add("screenshots")} />
      </Field>
      <FileList label="Screenshots" files={screenshots} errors={errors} onRemove={file => onChange({ screenshots: screenshots.filter(row => row !== file) })} />
    </div>
  </fieldset>;
}

export function filesReady(models: File[], accepted: string[]) {
  return models.length > 0 && models.every(file => !formatError(file, accepted));
}
