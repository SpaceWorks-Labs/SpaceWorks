import { t } from "@lingui/core/macro";
import type { CustomAnswerSnapshot, CustomAnswerSnapshotV2, CustomAnswerValue } from "./customFormTypes";
import type { ReactNode } from "react";

const ANSWER_TONES = [
  "border-accent bg-accent-soft",
  "border-line bg-accent-soft",
  "border-success bg-success-soft",
  "border-warn bg-warn-soft",
] as const;

function answerTone(id: string) {
  const total = [...id].reduce((sum, character) => sum + character.codePointAt(0)!, 0);
  return ANSWER_TONES[total % ANSWER_TONES.length];
}

function displayValue(value: CustomAnswerValue) {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

export function CustomAnswersView({ snapshot, viewer, renderFiles }: {
  snapshot: CustomAnswerSnapshot | CustomAnswerSnapshotV2 | null | undefined;
  viewer?: "owner" | "finance";
  renderFiles?: (answer: CustomAnswerSnapshotV2["answers"][number]) => ReactNode;
}) {
  if (!snapshot?.answers.length) {
    return <p className="text-sm text-muted">{t`No custom answers were submitted.`}</p>;
  }

  return (
    <dl className="grid gap-3">
      {snapshot.answers.filter(answer => !("sensitive" in answer && answer.sensitive) || viewer === "owner" || viewer === "finance").map((answer) => (
        <div key={answer.id} className={`rounded-lg border ${answerTone(answer.id)} p-3`}>
          <dt className="eyebrow">{answer.label}</dt>
          <dd className="mt-1 whitespace-pre-wrap break-words text-sm text-ink">{snapshot.version === 2 && answer.type === "file" && renderFiles ? renderFiles(answer as CustomAnswerSnapshotV2["answers"][number]) : snapshot.version === 2 ? displayV2(answer) : displayValue(answer.value as CustomAnswerValue)}</dd>
        </div>
      ))}
    </dl>
  );
}

function displayV2(answer: { type: string; value?: unknown }) {
  const value = answer.value;
  if (answer.type === "age_at_event" && value === undefined) return "See the authorized age projection for the event date.";
  if (answer.type === "asset_reference") return value ? "File attached" : "No file";
  if (answer.type === "file") return Array.isArray(value) ? `${value.length} file${value.length === 1 ? "" : "s"} attached` : "No files";
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const object = value as Record<string, unknown>;
    if (answer.type === "money") return Number.isSafeInteger(object.amount_minor) && typeof object.currency === "string" ? `${object.amount_minor} minor units (${object.currency})` : "Answer unavailable";
    if (answer.type === "itinerary") return [object.mode, object.origin, object.destination, object.depart_at, object.arrive_at].filter(item => typeof item === "string").join(" · ");
    if (answer.type === "emergency_contact") return [object.name, object.relationship, object.phone].filter(item => typeof item === "string").join(" · ");
    if (object.option_id) return [object.option_id, object.text].filter(Boolean).join(": ");
    if (Array.isArray(object.option_ids)) return [...object.option_ids, object.other_text].filter(item => typeof item === "string").join(", ");
    return "Answer unavailable";
  }
  return value === undefined || value === null ? "Not answered" : displayValue(value as CustomAnswerValue);
}
