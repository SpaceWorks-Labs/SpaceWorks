import type { ChangeEvent, Dispatch, SetStateAction } from "react";

import { EmptyState, ErrorBlock, Field, ListRow, ProgressBar, RelativeTime, Skeleton, StatusPill } from "../../components/ui";
import type { PrintStatus } from "./publicApi";
import { ServiceRequestEta } from "../machine-service/ServiceRequestEta";
import { normalizeServiceStatus } from "../machine-service/types";

export type TextInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
};

const steps = [
  { key: "pending", label: "Requested" },
  { key: "accepted", label: "Accepted" },
  { key: "in_progress", label: "Printing" },
  { key: "completed", label: "Ready to collect" },
  { key: "collected", label: "Collected" },
];

export function TextInput({
  label,
  value,
  onChange,
  required = false,
  type = "text",
}: TextInputProps) {
  return <Field label={label}><input className="desk-input w-full" required={required} type={type} value={value} onChange={event => onChange(event.target.value)} /></Field>;
}

export function TextArea({
  label,
  value,
  onChange,
}: TextInputProps) {
  return <Field label={label}><textarea className="desk-input min-h-24 w-full" value={value} onChange={event => onChange(event.target.value)} /></Field>;
}

export function FilePicker({
  label,
  accept,
  files,
  setFiles,
}: {
  label: string;
  accept: string;
  files: File[];
  setFiles: Dispatch<SetStateAction<File[]>>;
}) {
  function addFiles(event: ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? []);
    setFiles((current) => [...current, ...selected]);
    event.target.value = "";
  }

  return <div className="grid gap-3">
    <Field label={label} className="rounded-xl border border-dashed border-outline p-4">
      <input accept={accept} className="desk-input w-full" multiple type="file" onChange={addFiles} />
    </Field>
    {files.length ? <ul className="grid gap-3">{files.map((file, index) => <li key={`${file.name}-${file.lastModified}-${index}`}>
      <ListRow title={file.name} right={<button className="desk-button-ghost text-danger" type="button"
        onClick={() => setFiles(current => current.filter((_, fileIndex) => fileIndex !== index))}>Remove</button>} />
    </li>)}</ul> : <EmptyState message="No files added yet. Choose your print files above." />}
  </div>;
}

function queuePositionDetail(status: PrintStatus): string {
  const approvedAhead = status.queue_approved_ahead ?? 0;
  const awaitingReviewAhead = status.queue_awaiting_review_ahead ?? 0;
  const current = normalizeServiceStatus(status.status);
  // Only an approved job can be "next"; a pending one is still waiting for review.
  if (current === "accepted" && approvedAhead === 0) return "You're next among approved jobs";
  if (current === "pending" && approvedAhead === 0 && awaitingReviewAhead === 0) return "Awaiting review";
  return [
    `${approvedAhead} approved job${approvedAhead === 1 ? "" : "s"} ahead`,
    `${awaitingReviewAhead} awaiting review`,
  ].join(" / ");
}

export function StatusStepper({ status }: { status: PrintStatus }) {
  const current = normalizeServiceStatus(status.status);
  const currentIndex = steps.findIndex(step => step.key === current);
  if (current === "cancelled") return <StatusPill tone="neutral" label={`${status.title} was cancelled. Nothing was charged.`} />;
  if (current === "rejected" || current === "failed") return <StatusPill tone="danger" label={`${status.title} is ${current}.`} />;
  return <div className="grid gap-4">
    <ProgressBar value={Math.max(0, currentIndex) / (steps.length - 1)} label="Print progress" />
    <ol className="grid gap-2">{steps.map((step, index) => <li key={step.key} aria-current={index === currentIndex ? "step" : undefined}>
      <StatusPill label={step.label} tone={index < currentIndex ? "success" : index === currentIndex ? "accent" : "neutral"} />
    </li>)}</ol>
    {status.queue_position != null ? <ListRow title={`#${status.queue_position} in the queue`} meta={queuePositionDetail(status)} /> : null}
    <ServiceRequestEta eta={status.eta} status={current} showLine={false} />
    <p className="text-sm text-muted">Current status: <span className="font-semibold text-ink">{current.replace(/_/g, " ")}</span></p>
  </div>;
}

export function StatusResult({ isPending, error, status, onRetry }: {
  isPending: boolean; error: Error | null; status?: PrintStatus; onRetry?: () => void;
}) {
  if (isPending) return <div role="status" aria-label="Loading print status"><Skeleton className="h-60" /></div>;
  if (error) return <ErrorBlock error={new Error(error.message || "Couldn't load your print status. Try again.")} onRetry={onRetry} />;
  return status ? <div className="grid gap-5"><div><h3 className="title-section break-words">{status.title}</h3>
    <p className="mt-1 text-sm text-muted">Created <RelativeTime date={status.created_at} /></p></div><StatusStepper status={status} /></div> : null;
}
