import { useEffect, useRef, useState, type ReactNode } from "react";
import { ActionControl, Callout, Card, ConfirmDialog, Modal, PageHeader } from "../ui";
import type { Action, CalloutProps } from "../ui";
import { ResultPanel, type ResultPanelProps } from "../ui/ResultPanel";
import { FlowSteps, type FlowStep } from "./FlowSteps";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import type { LayoutProps } from "./types";

type Presentation = { presentation?: "page" | "kiosk"; open?: never } | { presentation: "dialog"; open: boolean };
export type FlowLayoutProps = LayoutProps & Presentation & {
  title: string;
  subject?: string;
  steps: FlowStep[];
  current: string;
  onStepSelect?: (key: string) => void;
  work: ReactNode;
  footer: { back?: Action; next: Action };
  onCancel: () => void;
  leaveGuard?: string;
  result?: ResultPanelProps;
  error?: CalloutProps;
  compact?: boolean;
  pending?: boolean;
};
export function FlowLayout({ title, subject, steps, current, onStepSelect, work, footer, onCancel, leaveGuard,
  result, error, compact, pending, presentation = "page", open, standalone = presentation === "page", width, ...query }: FlowLayoutProps) {
  const [confirmLeave, setConfirmLeave] = useState(false);
  const workRef = useRef<HTMLDivElement>(null);
  const previous = useRef(current);
  useEffect(() => {
    if (previous.current !== current) { workRef.current?.focus(); previous.current = current; }
  }, [current]);
  const busy = Boolean(pending || footer.next.pending || footer.back?.pending);
  const cancel = () => { if (!busy) { if (leaveGuard) setConfirmLeave(true); else onCancel(); } };
  const blocked = query.state.status !== "ready" || query.isEmpty;
  const next = { ...footer.next, disabled: footer.next.disabled || blocked,
    disabledReason: blocked ? "Wait until this step is ready." : footer.next.disabledReason ?? (footer.next.disabled ? "Complete this step before continuing." : undefined) };
  const content = <LayoutFrame standalone={presentation === "page" && standalone} width={width}
    className={presentation === "kiosk" ? "sw-kiosk-flow sw-overlay-content" : presentation === "dialog" ? "sw-overlay-content" : ""}>
    {presentation === "kiosk" ? <div className="mb-6"><h2 className="title-panel">{title}</h2>
      {subject ? <p className="mt-2 text-muted">{subject}</p> : null}</div>
      : <PageHeader headingLevel={presentation === "dialog" ? 2 : 1} title={title} subtitle={subject} />}
    <div className={steps.length > 1 && !compact && !result ? "sw-flow-columns" : "grid min-w-0 gap-6"}>
      {!result ? <FlowSteps steps={steps} current={current} onStepSelect={onStepSelect} /> : null}
      <div ref={workRef} tabIndex={-1} aria-label={steps.find(step => step.key === current)?.label ?? "Work panel"}
        className="min-w-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
        <QueryContent {...query}><Card>{result ? <ResultPanel {...result} /> : work}</Card></QueryContent>
        {error ? <div className="mt-4" role="alert"><Callout {...error} /></div> : null}
        {next.disabled && next.disabledReason && !result ? <p className="mt-4 text-sm text-muted">{next.disabledReason}</p> : null}
        <div className="sw-sticky-footer mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line bg-panel pt-4">
          <ActionControl action={{ label: "Cancel", onClick: cancel, disabled: busy }} />
          {!result ? <div className="ml-auto flex flex-wrap items-center justify-end gap-3">
            {footer.back ? <ActionControl action={footer.back} /> : null}<ActionControl primary action={next} />
          </div> : null}
        </div>
      </div>
    </div>
  </LayoutFrame>;
  return <>
    {presentation === "dialog" ? <Modal open={Boolean(open)} onClose={cancel} title={title} size="xl">{content}</Modal> : content}
    <ConfirmDialog open={confirmLeave} title="Leave this task?" message={leaveGuard ?? "Leave this task?"}
      confirmLabel="Leave task" cancelLabel="Keep working" onCancel={() => { if (!busy) setConfirmLeave(false); }}
      pending={busy} onConfirm={() => { if (!busy) { setConfirmLeave(false); onCancel(); } }} />
  </>;
}
