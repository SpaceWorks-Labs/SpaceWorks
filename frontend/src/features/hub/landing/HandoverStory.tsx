import { t } from "@lingui/core/macro";
import { Camera, Check, ClipboardCheck, PackageCheck, QrCode, RotateCcw, Send } from "lucide-react";
import { useState } from "react";

type Step = { key: string; label: string; who: string; proof: string; icon: typeof Send };

export function handoverSteps(): Step[] {
  return [
    { key: "requested", label: t`Requested`, who: t`A member, from the public catalogue`, proof: t`Signed-in account, dates and purpose`, icon: Send },
    { key: "accepted", label: t`Accepted`, who: t`Inventory staff, at the desk`, proof: t`Decision recorded with who and when`, icon: ClipboardCheck },
    { key: "issued", label: t`Issued`, who: t`Front desk`, proof: t`Box QR scanned and an issue photo taken`, icon: QrCode },
    { key: "returned", label: t`Returned`, who: t`Front desk`, proof: t`Return photo and a remark: “Tip worn, sent for repair”`, icon: Camera },
  ];
}

type Props = { reached?: number; onReach?: (reached: number) => void };

/**
 * A sample loan walking the real state machine (requested → accepted → issued → returned) with the
 * evidence each step needs. Sample data only: no API call, no real QR payload. Every row is drawn from
 * the start (unreached ones dimmed, their proof held back) so the card never changes height while it
 * sits in the sticky stage. Controlled by the scroll story through `reached`/`onReach`; on its own it
 * keeps its own state.
 */
export function HandoverStory({ reached: controlled, onReach }: Props) {
  const all = handoverSteps();
  const [own, setOwn] = useState(2);
  const reached = controlled ?? own;
  const go = (next: number) => { if (controlled === undefined) setOwn(next); onReach?.(next); };
  const done = reached >= all.length;
  const status = [t`Waiting for review`, t`Ready for pickup`, t`On loan`, t`Returned`][reached - 1];
  return <section aria-labelledby="handover-story-title" className="sw-hub-story">
    <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
      <div className="min-w-0">
        <h3 id="handover-story-title" className="title-section flex items-center gap-2"><PackageCheck size={18} aria-hidden="true" className="shrink-0" />{t`Loan · Soldering station SS-03`}</h3>
        <p className="mt-1 text-sm text-muted">{t`Sample record`}</p>
      </div>
      <span className={`inline-flex min-h-7 shrink-0 items-center rounded-full px-3 text-xs font-semibold ${done ? "bg-success text-on-success" : "bg-warn text-on-warn"}`}>
        {status}</span>
    </div>
    <ol className="grid" aria-live="polite">
      {all.map((step, index) => {
        const Icon = step.icon;
        const open = index < reached;
        return <li key={step.key} className="sw-hub-story-step" data-pending={open ? undefined : ""} data-new={index === reached - 1 || undefined}>
          <span className="sw-hub-story-dot" aria-hidden="true">{open ? <Icon size={16} /> : null}</span>
          <div className="min-w-0">
            <p className="font-semibold text-ink">{step.label}{open ? null : <span className="sr-only">{" "}{t`(not reached yet)`}</span>}</p>
            <p className="text-sm text-muted">{step.who}</p>
            <p className="sw-hub-story-proof mt-1 flex items-start gap-1.5 text-sm text-ink"><Check size={16} className="mt-0.5 shrink-0 text-success-ink" aria-hidden="true" />{step.proof}</p>
          </div>
        </li>;
      })}
    </ol>
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-surface px-5 py-4">
      <p className="text-sm text-muted">{done ? t`Four entries, written in order, never edited.` : t`No scan and photo, no handover.`}</p>
      {done
        ? <button type="button" className="desk-button gap-2" onClick={() => go(1)}><RotateCcw size={16} aria-hidden="true" />{t`Start again`}</button>
        : <button type="button" className="desk-button-primary" onClick={() => go(reached + 1)}>{t`Next step: ${all[reached].label}`}</button>}
    </div>
  </section>;
}
