import { t } from "@lingui/core/macro";
import { Link } from "react-router-dom";
import { moduleKeys, moduleLabel } from "../../../lib/moduleLabels";
import { featureCatalogue } from "../featuresPage/catalogue";
import { defaultLabel } from "../featuresPage/featureSummary";
import { moduleSlug } from "../featuresPage/moduleGroups";
import { moduleMoney, moduleWithout } from "../featuresPage/moduleLifecycle";

/** Reuses the feature catalogue: adding a live module adds it here as well as on /features. */
export function ModuleDirectory() {
  const catalogue = featureCatalogue();
  const without = moduleWithout();
  const keys = moduleKeys();
  return <section className="mt-16" aria-labelledby="landing-modules-title">
    <h3 id="landing-modules-title" className="title-section">{t`Every module, with or without it`}</h3>
    <p className="mt-4 max-w-3xl text-muted">{t`${keys.length} modules share one system. Six core modules always protect the handover workflow; the rest are optional. Switching a module off hides its surfaces and keeps its data. Deleting its rows is a separate superadmin action.`}</p>
    <p className="mt-4 max-w-3xl text-muted">{t`Maintenance, To-Buy, warranty and repairs are feature switches under their parent areas, rather than separate modules.`}</p>
    <Link to="/features" className="sw-hub-inline-link mt-4 inline-block">{t`Explore every module and feature switch`}</Link>
    <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {keys.map(key => <li key={key} data-landing-module={key} className="min-w-0 rounded-xl border border-line p-5">
        <h4 className="font-semibold text-ink"><Link to={`/features/${moduleSlug(key)}`} className="sw-hub-inline-link">{moduleLabel(key)}</Link></h4>
        <p className="mt-2 text-sm text-muted">{catalogue[key].value}</p>
        <p className="mt-3 text-xs font-semibold text-ink">{defaultLabel(key)}</p>
        <p className="mt-2 text-sm text-muted">{without[key]}</p>
        <details className="mt-4 text-sm text-muted">
          <summary className="cursor-pointer font-semibold text-ink">{t`What it adds and how it handles money`}</summary>
          <p className="mt-3">{catalogue[key].what}</p>
          <p className="mt-3">{moduleMoney(key)}</p>
        </details>
      </li>)}
    </ul>
  </section>;
}
