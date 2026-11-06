import { t } from "@lingui/core/macro";
import { Check, Circle } from "lucide-react";
import { useDelight } from "./DelightProvider";

export function StaffGreeting({ name, now = new Date() }: { name: string; now?: Date }) {
  const hour = now.getHours();
  return <p className="text-ink">{hour < 12 ? t`Good morning` : hour < 18 ? t`Good afternoon` : t`Good evening`}, {name}. What will you make possible today?</p>;
}
export function ConfirmationGreeting({ name }: { name: string }) { return <p className="text-ink">{t`You're in, ${name}.`}</p>; }

export type SetupStep = { key: "inventory" | "qr" | "staff" | "public"; label: string; done: boolean; href: string; available: boolean };
/** Caller derives availability from actual modules/actions; this never grants them. */
export function SetupChecklist({ steps }: { steps: SetupStep[] }) {
  const order: SetupStep["key"][] = ["inventory", "qr", "staff", "public"];
  const visible = [...steps].filter(step => step.available).sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  if (!visible.length || visible.every(step => step.done)) return null;
  return <section aria-label={t`Set up your space`} className="rounded-2xl border border-line bg-panel p-5">
    <h2 className="title-section">{t`Set up your space`}</h2><ol className="mt-3 grid gap-2">{visible.map(step => <li key={step.key}>
      <a href={step.href} className="flex min-h-11 items-center gap-3 rounded-control text-accent-ink underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
        {step.done ? <Check size={20} aria-hidden="true" /> : <Circle size={20} aria-hidden="true" />}<span>{step.label}{step.done ? t` — complete` : ""}</span>
      </a></li>)}</ol>
  </section>;
}

export type CountProjection = { mode: "exact_count"; count: number; total: number } | { mode: "status_only"; label: string } | { mode: "hidden" };
export function DotMeter({ value, noun = "available" }: { value: CountProjection; noun?: string }) {
  const { enabled } = useDelight();
  if (value.mode === "hidden") return null;
  if (value.mode === "status_only") return <p className="text-muted">{value.label}</p>;
  const total = Number.isFinite(value.total) ? Math.max(0, Math.trunc(value.total)) : 0;
  const count = Number.isFinite(value.count) ? Math.max(0, Math.min(total, Math.trunc(value.count))) : 0;
  const dots = Math.min(20, total);
  const filled = total ? Math.round(count / total * dots) : 0;
  return <div className="grid gap-2"><p className="text-ink">{`${count} of ${total} ${noun}`}</p>
    {enabled ? <div aria-hidden="true" className="flex flex-wrap gap-1">{Array.from({ length: dots }, (_, i) => <span key={i} className={`h-2 w-2 rounded-full ${i < filled ? "bg-accent" : "bg-line"}`} />)}</div> : null}</div>;
}

export function EventTimeChip({ startsAt, endsAt, now }: { startsAt: string; endsAt: string; now: Date }) {
  const start = Date.parse(startsAt), end = Date.parse(endsAt), time = now.getTime();
  if (![start, end, time].every(Number.isFinite) || end < start) return null;
  const label = time >= end ? "Ended" : time >= start ? "Happening now" : `Doors open in ${Math.ceil((start - time) / 3600000)} h`;
  return <span className="inline-flex rounded-full border border-line bg-panel px-3 py-1 text-sm text-ink">{label}</span>;
}
