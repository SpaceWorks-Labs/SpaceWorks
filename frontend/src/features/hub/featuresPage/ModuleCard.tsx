import { ArrowRight } from "lucide-react";
import type { ModuleKey } from "../../../lib/retiredModules";
import { moduleLabel } from "../../../lib/moduleLabels";
import { TransitionLink } from "../../../lib/motion";
import { featureCatalogue } from "./catalogue";
import { defaultLabel, moduleSummary, summaryLine } from "./featureSummary";
import { moduleDefault } from "./featureAreas";
import { moduleSlug } from "./moduleGroups";

/** One module on the overview: icon, name, one-line value, counts, and a link to its page. */
export function ModuleCard({ module, solo = false }: { module: ModuleKey; solo?: boolean }) {
  const entry = featureCatalogue()[module];
  const Icon = entry.icon;
  return <li data-module={module} data-solo={solo ? "true" : undefined} className="sw-features-card">
    <span className="sw-features-card-icon" aria-hidden="true"><Icon size={22} /></span>
    <h3 className="sw-features-card-title">
      <TransitionLink to={`/features/${moduleSlug(module)}`} className="sw-features-card-link">{moduleLabel(module)}</TransitionLink>
    </h3>
    <p className="text-muted">{entry.value}</p>
    <p className="sw-features-card-meta">
      <span>{summaryLine(moduleSummary(module))}</span>
      <span className="sw-features-default" data-default={moduleDefault(module)}>{defaultLabel(module)}</span>
    </p>
    <ArrowRight size={18} className="sw-features-card-arrow" aria-hidden="true" />
  </li>;
}
