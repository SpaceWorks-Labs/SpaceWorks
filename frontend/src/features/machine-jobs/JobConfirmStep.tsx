import type { JobDraft } from "./jobDraft";
import type { JobType } from "./types";

const ACKS: { key: keyof JobDraft["acks"]; text: string }[] = [
  { key: "pickup", text: "I'll collect it within 14 days of it being ready. After that it becomes the space's." },
  { key: "failure", text: "I understand jobs can fail. Staff will tell me what happened and whether a re-run or charge applies." },
  { key: "content", text: "I own this design or have the right to make it, and it is allowed in this space." },
];

/** Step 4: a last look at the job and the three promises the space asks for. */
export function JobConfirmStep({ type, draft, fileCount, screenshotCount, onAck, disabled }: {
  type: JobType; draft: JobDraft; fileCount: number; screenshotCount: number; disabled?: boolean;
  onAck: (key: keyof JobDraft["acks"], value: boolean) => void;
}) {
  const rows = [
    ["Machine", type.name], ["Title", draft.title.trim()], ["Copies", String(draft.copies)],
    ["Files", `${fileCount} design file${fileCount === 1 ? "" : "s"}${screenshotCount ? `, ${screenshotCount} screenshot${screenshotCount === 1 ? "" : "s"}` : ""}`],
    ...(draft.neededBy ? [["Needed by", new Date(`${draft.neededBy}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })]] : []),
    ["Material", draft.ownMaterial ? `My own${draft.materialNote.trim() ? `: ${draft.materialNote.trim()}` : ""}` : [draft.material, draft.color].filter(Boolean).join(", ") || "Staff choose"],
  ];
  return <div className="grid gap-5">
    <dl className="grid gap-2 text-sm">{rows.map(([label, value]) => <div key={label} className="grid grid-cols-[8rem_1fr] gap-3">
      <dt className="text-muted">{label}</dt><dd className="min-w-0 break-words text-ink">{value}</dd></div>)}</dl>
    {type.quotes !== "off" ? <p className="text-sm text-muted">If staff price this job, you'll get a quote to approve before it joins the queue.</p> : null}
    <fieldset className="grid gap-3" disabled={disabled}>
      <legend className="title-section mb-1">Before you send it</legend>
      {ACKS.map(ack => <label key={ack.key} className="flex min-h-11 items-start gap-3 text-sm text-ink">
        <input type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-brand" checked={draft.acks[ack.key]} onChange={event => onAck(ack.key, event.target.checked)} />
        <span>{ack.text}</span>
      </label>)}
    </fieldset>
  </div>;
}
