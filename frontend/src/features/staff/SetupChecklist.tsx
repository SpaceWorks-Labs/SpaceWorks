import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Icon, ProgressBar } from "../../components/ui";
import { readStorage, writeStorage } from "../../lib/safeStorage";
import { staffTabPath } from "./staffTabs";
import { setupSteps, type SetupState } from "./setupChecklistState";
import { useStaffGet, type Makerspace } from "./panels/shared";
import { FirstRunWizard } from "./firstRun/FirstRunWizard";
import { nothingSetUp, readWizardProgress } from "./firstRun/firstRunWizardState";
import { nounTitleOf } from "../../lib/spaceNoun";
import { LogoLoader } from "../../components/LogoLoader";

/**
 * The dashboard "Next steps" card. Completion comes from the server (setup-state), so the card
 * disappears by itself once every step is really done. The guided setup opens from here.
 */
export function SetupChecklist({ makerspace, owner, allowedTabs, guestOnly, singleTenantLocked }: {
  makerspace: Makerspace; owner: string; allowedTabs: readonly string[]; guestOnly: boolean; singleTenantLocked: boolean;
}) {
  const key = `spaceworks.setup.dismissed:${owner}:${makerspace.id}`;
  const [dismissed, setDismissed] = useState(() => readStorage(key) === "true");
  const [expanded, setExpanded] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const query = useStaffGet<SetupState>(["setup-state", makerspace.id], `/admin/makerspace/${makerspace.id}/setup-state`, !dismissed);
  const progress = readWizardProgress(owner, makerspace.id);
  const autoOpened = useRef(false);
  // A brand-new space opens the guided setup once; after that it waits for the button.
  useEffect(() => {
    if (autoOpened.current || !query.data || progress.started || !nothingSetUp(query.data)) return;
    autoOpened.current = true;
    setWizardOpen(true);
  }, [query.data, progress.started]);
  if (dismissed) return null;
  const steps = query.data ? setupSteps(query.data, makerspace.enabled_modules ?? []) : [];
  const done = steps.filter(step => step.complete).length;
  const nounTitle = nounTitleOf(makerspace);
  if (steps.length && done === steps.length && !wizardOpen) return null;
  const next = steps.find(step => !step.complete && allowedTabs.includes(step.tab));
  const href = (tab: string, section = "") => consoleSessionHref(staffTabPath(tab, guestOnly, makerspace.slug, singleTenantLocked, section));
  return <section className="rounded-xl border border-warn bg-warn-soft p-5 text-warn-ink" aria-labelledby="setup-heading">
    {wizardOpen ? <FirstRunWizard makerspace={makerspace} owner={owner} state={query.data} onClose={() => setWizardOpen(false)} /> : null}
    <div className="flex flex-wrap items-start gap-3">
      <Icon name="TriangleAlert" />
      <div className="min-w-0 flex-1">
        <h2 id="setup-heading" className="text-sm font-semibold">{t`Next steps for ${makerspace.name}`}{steps.length ? t` — ${done} of ${steps.length} done` : ""}</h2>
        <p className="mt-1 text-sm">{t`Ticks appear as you set things up; this card goes away when everything is done.`}</p>
      </div>
      <button className="desk-button-ghost" type="button" aria-label={t`Hide setup checklist`} onClick={() => { writeStorage(key, "true"); setDismissed(true); }}>{t`Hide`}</button>
    </div>
    {query.isLoading ? <LogoLoader label={t`Checking setup…`} size={48} className="min-h-16 py-3" /> : null}
    {query.error ? <p role="alert" className="mt-3 text-sm text-danger">{t`Could not check setup: ${query.error.message}`}</p> : null}
    {steps.length ? <div className="mt-4 grid gap-3">
      <ProgressBar label={t`${nounTitle} setup`} value={done / steps.length} />
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="desk-button-primary" onClick={() => setWizardOpen(true)}>
          {progress.started && !progress.finished ? t`Continue guided setup` : t`Start guided setup`}</button>
        {next ? <Link className="w-fit rounded-control text-sm underline focus-visible:outline-2 focus-visible:outline-focus" to={href(next.tab, "section" in next ? next.section : "")}>{next.label} →</Link> : null}
      </div>
      <div>
        <button type="button" aria-expanded={expanded} aria-controls="setup-steps" onClick={() => setExpanded(value => !value)} className="min-h-11 cursor-pointer rounded-control py-2 text-sm focus-visible:outline-2 focus-visible:outline-focus">{t`All setup steps`}</button>
        {expanded ? <ul id="setup-steps" className="grid gap-2">{steps.map(step => <li key={step.key} className="flex items-center gap-3 text-sm">
          <span>{step.complete ? t`Done` : t`To do`}</span>
          {allowedTabs.includes(step.tab) ? <Link className="rounded-control underline focus-visible:outline-2 focus-visible:outline-focus" to={href(step.tab, "section" in step ? step.section : "")}>{step.label}</Link> : <span>{t`${step.label} · ask an administrator`}</span>}
        </li>)}</ul> : null}
      </div>
    </div> : null}
  </section>;
}
