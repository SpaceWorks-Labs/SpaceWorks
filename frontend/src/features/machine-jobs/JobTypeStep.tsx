import type { JobType } from "./types";

const QUOTE_HINT: Record<JobType["quotes"], string> = {
  off: "",
  auto: "If the job is priced, you approve a quote before it joins the queue.",
  above: "Larger jobs get a quote for you to approve first.",
  always: "Every job gets a quote for you to approve first.",
};

export function extensionList(type: JobType) {
  return type.accepted_extensions.map(ext => (ext.startsWith(".") ? ext : `.${ext}`).toLowerCase());
}

/**
 * `?queue=<id>` or `?type=<machine type id | slug | "printer">` picks a type up front, so the
 * machines page and the old 3D-print links land on the right form.
 */
export function preselectType(types: JobType[], params: URLSearchParams): JobType | undefined {
  const queue = params.get("queue");
  if (queue) return types.find(type => String(type.queue_id) === queue);
  const wanted = params.get("type")?.trim().toLowerCase();
  if (!wanted) return types.length === 1 ? types[0] : undefined;
  if (["printer", "3d-printer", "3d_printer"].includes(wanted)) return types.find(type => type.is_printer);
  return types.find(type => String(type.machine_type_id) === wanted || type.machine_type_slug.toLowerCase() === wanted);
}

/**
 * Step 1: which machine type. Each option says what it accepts and how it is run and priced.
 * `showPrice` false (machine charges off, #184) drops the quote and prepay lines.
 */
export function JobTypeStep({ types, value, onChange, showPrice = true }: { types: JobType[]; value: number | null; onChange: (queueId: number) => void; showPrice?: boolean }) {
  return <fieldset className="grid gap-3">
    <legend className="title-section mb-1">What should make it?</legend>
    <p className="text-sm text-muted">Pick the kind of machine. Staff choose the exact machine when your job runs.</p>
    {types.map(type => {
      const hints = [showPrice ? QUOTE_HINT[type.quotes] : "", showPrice && type.prepay ? "Paid before the job runs." : "",
        type.runs_unattended ? "Runs unattended — it may finish while nobody is at the machine." : "",
        type.max_open_jobs ? `Up to ${type.max_open_jobs} open job${type.max_open_jobs === 1 ? "" : "s"} per member.` : ""].filter(Boolean);
      const selected = value === type.queue_id;
      return <label key={type.queue_id} className={`flex min-h-11 cursor-pointer items-start gap-3 rounded-control border p-4 ${selected ? "border-accent bg-accent-soft" : "border-line"}`}>
        <input type="radio" name="job-type" className="mt-1 h-5 w-5 shrink-0 accent-brand" checked={selected} onChange={() => onChange(type.queue_id)} />
        <span className="grid min-w-0 gap-1">
          <span className="font-semibold text-ink">{type.name}{type.name !== type.machine_type_name ? <span className="font-normal text-muted"> · {type.machine_type_name}</span> : null}</span>
          <span className="break-words text-sm text-muted">{extensionList(type).length ? `Accepts ${extensionList(type).join(", ")}` : "Ask staff which files this machine takes."}</span>
          {hints.map(hint => <span key={hint} className="text-sm text-ink">{hint}</span>)}
        </span>
      </label>;
    })}
  </fieldset>;
}
