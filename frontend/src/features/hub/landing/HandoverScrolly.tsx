import { t } from "@lingui/core/macro";
import { useRef } from "react";
import { HandoverStory, handoverSteps } from "./HandoverStory";
import { useActiveStep } from "./useInView";

const STICKY = "(min-width: 1024px) and (min-height: 640px)";

function narrative() {
  return [
    { title: t`A member asks from the catalogue`, body: t`They sign in, choose dates and say what it is for. Nothing is promised until someone at the desk decides.` },
    { title: t`Staff decide at the desk`, body: t`Accepting reserves the stock, so two people are never promised the same drill. The decision is recorded with who and when.` },
    { title: t`Scan and photograph at handover`, body: t`The box QR scan and an issue photo are both required. Without them, the item cannot be issued.` },
    { title: t`Back with a photo and a remark`, body: t`The return needs a photo and a note on its condition. Damage or a missing part closes the loan with an issue on the borrower’s record.` },
  ];
}

/**
 * Scrollytelling: four steps scroll past while the sample loan stays pinned beside them and moves to
 * whichever step crosses the middle of the screen (`aria-current="step"` marks it). The record's own
 * buttons still work, and on wide screens they scroll the matching step into place. Below 1024px, or on
 * a short screen, the stage is not pinned: the steps read as a list and the record follows it.
 */
export function HandoverScrolly() {
  const steps = handoverSteps();
  const copy = narrative();
  const list = useRef<HTMLOListElement>(null);
  const [active, setActive] = useActiveStep(list);
  const reach = (reached: number) => {
    const index = reached - 1;
    setActive(index);
    const node = list.current?.querySelector<HTMLElement>(`[data-step="${index}"]`);
    if (!node || !window.matchMedia?.(STICKY).matches) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    node.scrollIntoView?.({ block: "center", behavior: still ? "auto" : "smooth" });
  };
  return <section id="handover" aria-labelledby="handover-title" className="sw-hub-section">
    <div className="sw-hub-wrap">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-end md:gap-10">
        <h2 id="handover-title" className="sw-hub-h2">{t`Every handover, on the record.`}</h2>
        <p className="sw-hub-lede">{t`Follow one sample loan from request to return. It moves forward only with the proof each step needs.`}</p>
      </div>
      <div className="sw-hub-scrolly">
        <ol ref={list} className="sw-hub-scrolly-steps">
          {steps.map((step, index) => <li key={step.key} data-step={index} aria-current={index === active ? "step" : undefined} className="sw-hub-scrolly-step">
            <span className="sw-hub-scrolly-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
            <p className="sw-hub-scrolly-state">{step.label}</p>
            <h3 className="sw-hub-scrolly-title">{copy[index].title}</h3>
            <p className="sw-hub-scrolly-body">{copy[index].body}</p>
          </li>)}
        </ol>
        <div className="sw-hub-scrolly-stage">
          <div className="sw-hub-scrolly-pin"><HandoverStory reached={active + 1} onReach={reach} /></div>
        </div>
      </div>
    </div>
  </section>;
}
