import { useRef, useState, type KeyboardEvent } from "react";
import { CollapsibleSection, Icon } from "../ui";
import { useLayoutMedia } from "./useLayoutMedia";

export type FlowStep = { key: string; label: string; state: "done" | "current" | "todo";
  summary?: string; required?: boolean; missing?: boolean };
export function FlowSteps({ steps, current, onStepSelect }: { steps: FlowStep[]; current: string; onStepSelect?: (key: string) => void }) {
  const [open, setOpen] = useState(false);
  // The full rail only beside the work panel (xl two-column flow); a collapsed summary below that.
  const tablet = useLayoutMedia("(min-width: 1280px)");
  const navRef = useRef<HTMLElement>(null);
  const index = Math.max(0, steps.findIndex(step => step.key === current));
  const summary = `Step ${index + 1} of ${steps.length} · ${steps[index]?.label ?? ""}`;
  const moveFocus = (event: KeyboardEvent) => {
    if (!["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = Array.from(navRef.current?.querySelectorAll("button") ?? []);
    if (!buttons.length) return;
    const focused = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
      : (focused + (event.key === "ArrowUp" || event.key === "ArrowLeft" ? -1 : 1) + buttons.length) % buttons.length;
    event.preventDefault(); buttons[next]?.focus();
  };
  const rail = <nav ref={navRef} aria-label="Flow steps" onKeyDown={moveFocus}>
    <ol className="grid gap-3 md:flex md:flex-wrap xl:grid">{steps.map((step, i) => <li key={step.key}
      aria-current={step.key === current ? "step" : undefined} className="min-w-0">
      <div className={`flex min-h-11 items-start gap-3 rounded-control border p-3 ${step.key === current ? "border-accent bg-accent-soft text-accent-ink" : "border-line text-ink"}`}>
        <span aria-hidden="true">{step.state === "done" ? <Icon name="Check" /> : i + 1}</span>
        <div className="min-w-0 flex-1">
          {step.state === "done" && onStepSelect ? <button type="button" className="desk-button-ghost w-full justify-start text-left"
            onClick={() => onStepSelect(step.key)}>{step.label}</button> : <p className="font-semibold">{step.label}</p>}
          <p className="text-sm">{step.state === "done" ? "Completed" : step.key === current ? "Current step" : "Not started"}{step.required ? " · Required" : ""}</p>
          {step.summary ? <p className="mt-1 break-words text-sm">{step.summary}</p> : null}
          {step.missing ? <p className="mt-1 text-sm text-danger">Required information missing</p> : null}
        </div>
      </div>
    </li>)}</ol>
  </nav>;
  if (steps.length <= 1) return null;
  return tablet ? rail : <CollapsibleSection title={summary} open={open} onToggle={() => setOpen(!open)}>{rail}</CollapsibleSection>;
}
