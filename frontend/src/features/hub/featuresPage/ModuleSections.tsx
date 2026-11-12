import { t } from "@lingui/core/macro";
import { Check } from "lucide-react";
import type { ReactNode } from "react";
import type { FeatureDefinition } from "../../../lib/features";
import { featureHelp } from "../../../lib/featureHelp";
import { familyLabel } from "./featureSummary";
import { featureFamilies } from "./moduleFeatures";

/** A titled panel on a module page. `kind` is the test and styling hook. */
export function Panel({ kind, title, note, wide, children }: { kind: string; title: string; note?: string; wide?: boolean; children: ReactNode }) {
  return <section data-panel={kind} data-wide={wide ? "true" : undefined} aria-labelledby={`panel-${kind}`} className="sw-features-panel">
    <h2 id={`panel-${kind}`} className="title-section">{title}</h2>
    {children}
    {note ? <p className="text-sm text-muted">{note}</p> : null}
  </section>;
}

/** A plain list of lines, or why there is none. */
export function Lines({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="text-muted">{empty}</p>;
  return <ul className="sw-features-lines" data-wide={items.length > 8 ? "true" : undefined}>{items.map(item => <li key={item}>
    <Check size={16} className="mt-1 shrink-0 text-accent-ink" aria-hidden="true" />{item}</li>)}</ul>;
}

/** Every feature switch of the module, grouped by key family when it spans more than one. */
export function FeatureList({ features }: { features: FeatureDefinition[] }) {
  if (!features.length) return <p className="text-muted">{t`This module has no separate switches; it is on or off as a whole.`}</p>;
  const families = featureFamilies(features);
  return <div className="grid gap-6">{families.map(({ family, features: list }) => <div key={family}>
    {families.length > 1 ? <h3 className="sw-features-family">{familyLabel(family)}</h3> : null}
    <ul className="sw-features-switch-list">{list.map(feature => <li key={feature.key} data-feature={feature.key}>
      <span className="font-semibold text-ink">{feature.label}</span>
      {featureHelp(feature.key) ? <span className="text-sm text-muted">{featureHelp(feature.key)}</span> : null}
    </li>)}</ul>
  </div>)}</div>;
}
