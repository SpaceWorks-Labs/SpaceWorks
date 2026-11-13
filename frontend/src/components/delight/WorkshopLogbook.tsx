import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { useDelight, useReducedMotion } from "./DelightProvider";
import "./delight.css";

export function WorkshopLogbook() {
  const [open, setOpen] = useState(false);
  const id = useId();
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  if (!enabled) return null;
  return <section className="mt-8 rounded-2xl border border-line bg-panel p-5">
    <button type="button" className="desk-button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>{open ? t`Close` : t`Open`} {t` the workshop logbook`}</button>
    {open ? <article id={id} className={`mt-5 grid gap-3 text-ink ${reduced ? "" : "sw-delight-logbook"}`}>
      <h2 className="title-section">{t`A place for the next maker`}</h2>
      <p>{t`A shared workshop starts with a simple promise: leave the tools ready for the next person.`}</p>
      <p>{t`Space Works keeps that promise visible. A request becomes a handover, a handover leaves a record, and a returned tool makes room for another idea.`}</p>
      <p>{t`Built in the open, for the people who keep community workshops running.`}</p>
    </article> : null}
  </section>;
}
