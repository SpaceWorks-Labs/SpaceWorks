import { t } from "@lingui/core/macro";
import { Link, useLocation } from "react-router-dom";
import { SettingsRow } from "../../components/ui";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { FEATURE_DEFINITIONS, featureGroup, isSecurityFeature } from "../../lib/features";
import { RETIRED_FEATURES } from "../../lib/retiredFeatures";
import { moduleLabel } from "../../lib/moduleLabels";
import { staffPathState, staffTabPath } from "./staffTabs";
import type { Makerspace } from "./panels/shared";

type Props = { makerspace: Makerspace; settings?: Makerspace; loading: boolean };

/**
 * One way to switch features: the Areas & add-ons screen. This is only the summary and the way in,
 * with a deep link to each area's card (`?module=<key>` opens and scrolls to it).
 */
export function MakerspaceFeatureSettings({ makerspace, settings }: Props) {
  const { pathname } = useLocation();
  const guest = pathname.startsWith("/guest-admin");
  const base = staffTabPath("modules", guest, staffPathState(pathname, guest).makerspaceSlug || null);
  const enabled = new Set(settings?.enabled_features ?? makerspace.enabled_features ?? []);
  const areas = new Map<string, { on: number; total: number }>();
  for (const feature of FEATURE_DEFINITIONS) {
    if (isSecurityFeature(feature.key) || RETIRED_FEATURES.has(feature.key)) continue;
    const group = featureGroup(feature);
    const entry = areas.get(group) ?? { on: 0, total: 0 };
    areas.set(group, { on: entry.on + (enabled.has(feature.key) ? 1 : 0), total: entry.total + 1 });
  }
  const link = (module: string) => consoleSessionHref(`${base}?module=${module}`);
  return <SettingsRow label={t`Feature settings`} helper={t`Areas and the features inside them are switched on or off in one place: Areas & add-ons. Switching one off hides it and keeps its data.`}>
    <div className="grid min-w-0 gap-3">
      <Link className="desk-button w-fit" to={consoleSessionHref(base)}>{t`Open Areas & add-ons`}</Link>
      <ul aria-label={t`Features by area`} className="grid gap-1 text-sm">
        {[...areas].filter(([, count]) => count.on > 0).map(([area, count]) => <li key={area} className="flex min-h-11 flex-wrap items-center justify-between gap-2 border-t border-line first:border-0">
          <Link className="font-semibold text-ink underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" to={link(area)}>{area === "inventory" ? t`Inventory` : area === "general" ? t`General` : moduleLabel(area)}</Link>
          <span className="text-muted">{t`${count.on} of ${count.total} on`}</span>
        </li>)}
      </ul>
    </div>
  </SettingsRow>;
}
