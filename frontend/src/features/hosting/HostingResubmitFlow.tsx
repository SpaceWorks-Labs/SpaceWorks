import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FlowLayout } from "../../components/layouts";
import { Field } from "../../components/ui";
import { useResubmitHostingRequest, type HostingRequestDetails, type HostingResubmitBody } from "./hostingApi";

const FIELDS = (organization: boolean): { key: keyof HostingResubmitBody; label: string; long?: boolean }[] => [
  { key: "space_name", label: organization ? t`Organization name` : t`Makerspace name` },
  { key: "location", label: organization ? t`Where you meet (optional)` : t`Location` },
  { key: "space_website_url", label: t`Website (optional)` },
  { key: "description", label: organization ? t`About the organization` : t`About the space`, long: true },
];

/** X31: the applicant edits after "changes requested" and sends the request back to review. */
export function HostingResubmitFlow({ token, request, onDone }: { token: string; request: HostingRequestDetails; onDone: () => void }) {
  const [step, setStep] = useState<"edit" | "review">("edit");
  const [value, setValue] = useState<HostingResubmitBody>({ space_name: request.space_name, location: request.location ?? "",
    space_website_url: request.space_website_url ?? "", description: request.description ?? "", note: "" });
  const resubmit = useResubmitHostingRequest();
  // Decision 295: an organization request is worded for an organization.
  const fields = FIELDS(request.requested_kind === "organization");
  const tooShort = (value.description ?? "").trim().length < 20 || (value.space_name ?? "").trim().length < 2;
  const input = (key: keyof HostingResubmitBody) => ({ className: "desk-input", value: value[key] ?? "",
    onChange: (event: { target: { value: string } }) => setValue({ ...value, [key]: event.target.value }) });
  return <FlowLayout title={t`Update your hosting request`} subject={request.space_name} state={{ status: "ready" }} current={step}
    steps={[{ key: "edit", label: t`Make the changes`, state: step === "edit" ? "current" : "done", required: true },
      { key: "review", label: t`Send it back for review`, state: step === "review" ? "current" : "todo", required: true }]}
    onCancel={onDone}
    footer={step === "edit"
      ? { next: { label: t`Review changes`, disabled: tooShort, disabledReason: "Give a name and a description of at least 20 characters.", onClick: () => setStep("review") } }
      : { back: { label: t`Back`, onClick: () => setStep("edit") },
        next: { label: t`Send for review`, pending: resubmit.isPending, onClick: () => resubmit.mutate({ token, ...value }) } }}
    error={resubmit.isError ? { size: "panel", tone: "danger", lead: "Couldn't send your changes.", body: resubmit.error instanceof Error ? resubmit.error.message : t`Try again.` } : undefined}
    result={resubmit.isSuccess ? { tone: "success", title: t`Sent back for review`, summary: t`The platform team will look at your changes and reply by email.`,
      next: { label: t`See the request`, onClick: onDone } } : undefined}
    work={step === "edit" ? <div className="grid gap-4">
      <div className="rounded-xl border border-line bg-info-soft p-3 text-sm"><p className="font-semibold text-ink">{t`What to change`}</p><p className="mt-1 whitespace-pre-wrap">{request.changes_note}</p></div>
      {fields.map(field => <Field key={field.key} label={field.label}>
        {field.long ? <textarea {...input(field.key)} className="desk-input min-h-32" minLength={20} maxLength={2000} required />
          : <input {...input(field.key)} type={field.key === "space_website_url" ? "url" : "text"} maxLength={200} />}
      </Field>)}
      <Field label={t`A note for the reviewer (optional)`}><textarea {...input("note")} className="desk-input min-h-24" maxLength={2000} /></Field>
    </div> : <dl className="grid gap-3 text-sm">{fields.map(field => <div key={field.key} className="grid gap-1">
      <dt className="text-muted">{field.label}</dt><dd className="whitespace-pre-wrap break-words text-ink">{value[field.key] || "—"}</dd></div>)}
      {value.note ? <div className="grid gap-1"><dt className="text-muted">{t`Your note`}</dt><dd className="whitespace-pre-wrap">{value.note}</dd></div> : null}</dl>} />;
}
