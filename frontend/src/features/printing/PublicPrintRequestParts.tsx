import type { ChangeEvent, Dispatch, SetStateAction } from "react";
import { useEffect, useState } from "react";

import { EmptyState, ErrorBlock, Field, ListRow, ProgressBar, RelativeTime, Skeleton, StatusPill } from "../../components/ui";
import type { PrintStatus } from "./publicApi";

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

function printTimeLeftLabel(status: PrintStatus, now: number): string | null {
  if (
    status.status !== "in_progress" ||
    !status.started_at ||
    status.estimated_minutes == null
  ) {
    return null;
  }
  const finish = new Date(status.started_at).getTime() + status.estimated_minutes * 60_000;
  const remainingMs = finish - now;
  if (remainingMs <= 0) {
    return "Finishing up - past the estimate";
  }
  const totalMinutes = Math.ceil(remainingMs / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `~${hours}h ${minutes}m left` : `~${minutes}m left`;
}

function queuePositionDetail(status: PrintStatus): string {
  const approvedAhead = status.queue_approved_ahead ?? 0;
  const awaitingReviewAhead = status.queue_awaiting_review_ahead ?? 0;
  if (approvedAhead === 0 && awaitingReviewAhead === 0) {
    return "You're next in line";
  }
  return [
    `${approvedAhead} approved job${approvedAhead === 1 ? "" : "s"} ahead`,
    `${awaitingReviewAhead} awaiting review`,
  ].join(" / ");
}

export function StatusStepper({ status }: { status: PrintStatus }) {
  const currentIndex = steps.findIndex(step => step.key === status.status);
  const terminalError = status.status === "rejected" || status.status === "failed";
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (status.status !== "in_progress") return;
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, [status.status]);
  const timeLeft = printTimeLeftLabel(status, now);
  if (terminalError) return <StatusPill tone="danger" label={`${status.title} is ${status.status}.`} />;
  return <div className="grid gap-4">
    <ProgressBar value={Math.max(0, currentIndex) / (steps.length - 1)} label="Print progress" />
    <ol className="grid gap-2">{steps.map((step, index) => <li key={step.key} aria-current={index === currentIndex ? "step" : undefined}>
      <StatusPill label={step.label} tone={index < currentIndex ? "success" : index === currentIndex ? "accent" : "neutral"} />
    </li>)}</ol>
    {status.queue_position != null ? <ListRow title={`#${status.queue_position} in the queue`} meta={queuePositionDetail(status)} /> : null}
    {timeLeft ? <StatusPill label={timeLeft} tone="info" /> : null}
    <p className="text-sm text-muted">Current status: <span className="font-semibold text-ink">{status.status.replace(/_/g, " ")}</span></p>
  </div>;
}

export function StatusResult({ isPending, error, status, onRetry }: {
  isPending: boolean; error: Error | null; status?: PrintStatus; onRetry?: () => void;
}) {
  if (isPending) return <div role="status" aria-label="Loading print status"><Skeleton className="h-60" /></div>;
  if (error) return <ErrorBlock error={new Error("Couldn't load your print status. Try again.")} onRetry={onRetry} />;
  return status ? <div className="grid gap-5"><div><h3 className="title-section break-words">{status.title}</h3>
    <p className="mt-1 text-sm text-muted">Created <RelativeTime date={status.created_at} /></p></div><StatusStepper status={status} /></div> : null;
}
