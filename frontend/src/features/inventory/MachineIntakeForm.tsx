import { Modal } from "../../components/ui";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { tenantPublicRequest } from "../../lib/api";
import { PricePreview } from "../payments/PricePreview";

type IntakeField = { key: string; label: string; type: "text" | "number" | "integer" | "choice" | "boolean"; required?: boolean; choices?: string[]; min?: number; max?: number };
export type TypeIntake = { materials: { id: number | null; name: string; colours: string[] }[]; intake_schema: { version?: number; fields?: IntakeField[] } };
export type IntakeValues = Record<string, string | number | boolean>;

/** The type's typed intake answers as the server expects them; unticked booleans are sent as false. */
export function intakePayload(intake: TypeIntake | undefined, values: IntakeValues) {
  if (!intake?.intake_schema.version) return undefined;
  return { schema_version: intake.intake_schema.version, values: {
    ...Object.fromEntries((intake.intake_schema.fields ?? []).filter(f => f.type === "boolean").map(f => [f.key, false])), ...values,
  } };
}

/** One input per intake-schema field; shared by the per-machine dialog and the "Request a job" flow. */
export function IntakeFields({ intake, values, setValues }: {
  intake: TypeIntake | undefined; values: IntakeValues; setValues: (update: (current: IntakeValues) => IntakeValues) => void;
}) {
  return <>{intake?.intake_schema.fields?.map(field => <label key={field.key} className={field.type === "boolean" ? "flex min-h-11 flex-row-reverse items-center justify-end gap-3 text-sm" : "grid gap-1 text-sm"}>{field.label}
    {field.type === "choice" ? <select className="desk-input" required={field.required} value={String(values[field.key] ?? "")} onChange={event => setValues(v => { const next = { ...v }; if (event.target.value) next[field.key] = event.target.value; else delete next[field.key]; return next; })}><option value="">Choose</option>{field.choices?.map(c => <option key={c}>{c}</option>)}</select> :
      <input className={field.type === "boolean" ? "h-5 w-5 shrink-0 accent-brand" : "desk-input"} type={field.type === "boolean" ? "checkbox" : field.type === "text" ? "text" : "number"}
        required={field.required && field.type !== "boolean"} min={field.min} max={field.max} step={field.type === "integer" ? 1 : "any"}
        checked={field.type === "boolean" ? Boolean(values[field.key]) : undefined}
        value={field.type === "boolean" ? undefined : String(values[field.key] ?? "")}
        onChange={event => setValues(v => {
          const next = { ...v };
          if (field.type !== "boolean" && event.target.value === "") delete next[field.key];
          else next[field.key] = field.type === "boolean" ? event.target.checked : field.type === "text" ? event.target.value : Number(event.target.value);
          return next;
        })} />}
  </label>)}</>;
}

export function MachineIntakeForm({ slug, machineId, typeId, dialog = false, trackingPath }: {
  slug: string; machineId: number; typeId: number; dialog?: boolean;
  /** Tenant-aware status page path for the returned tracking token. */
  trackingPath?: (publicToken: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [values, setValues] = useState<IntakeValues>({});
  const schema = useQuery({ queryKey: ["machine-intake", slug, typeId],
    queryFn: () => tenantPublicRequest<TypeIntake>(slug, `/public/${encodeURIComponent(slug)}/machine-types/${typeId}/intake`) });
  const submit = useMutation({ mutationFn: () => tenantPublicRequest<{ status: string; public_token: string }>(slug,
    `/public/${encodeURIComponent(slug)}/machine-service-requests`, { method: "POST", body: JSON.stringify({
      machine_id: machineId, title, capability_payload: intakePayload(schema.data, values) ?? {},
    }) }) });
  if (schema.data && !schema.data.intake_schema.version) return null;
  const form = <form className="mt-3 grid gap-2" onSubmit={event => { event.preventDefault(); submit.mutate(); }}>
    <label className="grid gap-1 text-sm">Job title<input className="desk-input" required maxLength={200} value={title} onChange={event => setTitle(event.target.value)} /></label>
    <IntakeFields intake={schema.data} values={values} setValues={setValues} />
    <PricePreview makerspaceSlug={slug} request={{ domain: "machines", machine_id: machineId }} />
    {schema.isPending ? <p role="status">Loading job requirements…</p> : null}
    {schema.error || submit.error ? <p role="alert" className="text-sm text-danger">{(schema.error || submit.error)?.message}</p> : null}
    {submit.isSuccess ? <div role="status" className="grid gap-2"><p>Request submitted for review.</p>
      {submit.data?.public_token && trackingPath ? <Link className="desk-button" to={trackingPath(submit.data.public_token)}>Track your job</Link> : null}
      <p className="text-xs text-muted">Keep the tracking link private.</p></div> : <button className="desk-button-brand" disabled={submit.isPending || !schema.data}>Request work</button>}
  </form>;
  return dialog ? <><button className="desk-button mt-3" type="button" onClick={() => setOpen(true)}>Request a job</button>
    <Modal open={open} onClose={() => setOpen(false)} title="Request a job">{form}</Modal></> : form;
}
