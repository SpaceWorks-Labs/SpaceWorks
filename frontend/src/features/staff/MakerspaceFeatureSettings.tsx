import { t } from "@lingui/core/macro";
import { toast } from "../../components/ui/toastStore";
import { SettingsRow } from "../../components/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { FEATURE_DEFINITIONS, featureGroup, isSecurityFeature } from "../../lib/features";
import type { Makerspace } from "./panels/shared";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

// Parentless features are never gated by a module. The inventory family (inventory.*,
// loans.*) is listed under "Inventory" (#97, C-9); the rest under "General".
const PARENTLESS = new Set(["inventory", "general"]);
const GROUP_LABELS: Record<string, string> = { inventory: t`Inventory`, general: t`General`, machines: t`Machines`, bookings: t`Bookings` };

const MODULE_FEATURES = Object.entries(
  FEATURE_DEFINITIONS.filter(feature => !isSecurityFeature(feature.key)).reduce<Record<string, typeof FEATURE_DEFINITIONS>>((groups, feature) => {
    const group = featureGroup(feature);
    groups[group] = [...(groups[group] ?? []), feature];
    return groups;
  }, {}),
);

export function MakerspaceFeatureSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const enabledModules = settings?.enabled_modules ?? makerspace.enabled_modules ?? [];
  const enabledFeatures = settings?.enabled_features ?? makerspace.enabled_features ?? [];
  const update = useMutation({
    mutationFn: (next: string[]) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled_features: next }),
      }),
    onSuccess: async (_data, next) => { await (() => {
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    })(); toast(next.length ? t`Features updated.` : t`All features turned off.`, { undo: async () => { await ((next: string[]) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled_features: next }),
      }))(enabledFeatures); await (() => {
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    })(); } }); },
  });

  const toggleFeature = (key: string, checked: boolean) => {
    const next = checked
      ? [...enabledFeatures, key]
      : enabledFeatures.filter((feature) => feature !== key);
    update.mutate(next);
  };

  return (
    <SettingsRow label={t`Feature settings`} helper={t`Switch modules on or off under Modules. Each feature below has its own switch; turning one off keeps its data.`}><div className="@container grid min-w-0 gap-4">
      <div className="grid min-w-0 gap-2">


        <div className="flex flex-wrap gap-2">
          {enabledModules.map((module) => <Badge label="" key={module} tone="neutral">{module}</Badge>)}
        </div>
        {update.error ? <p className="text-sm text-danger" role="alert">{update.error.message}</p> : null}
      </div>
      <div className="mt-4 grid gap-3">
        {MODULE_FEATURES.map(([module, features]) => {
          const isGeneral = PARENTLESS.has(module);
          const moduleEnabled = isGeneral || enabledModules.includes(module);
          return (
            <fieldset key={module} className="grid gap-2 rounded border border-line p-3">
              <legend className="px-1 text-sm font-semibold text-ink">{GROUP_LABELS[module] ?? module}</legend>
              {!moduleEnabled ? <p className="text-sm text-muted">{t`Turn the module on under Modules to use these.`}</p> : null}
              {features.map((feature) => (
                <label key={feature.key} className="min-h-11 flex items-start gap-3 text-sm text-ink">
                  <input
                    className="mt-1 h-4 w-4"
                    type="checkbox"
                    checked={enabledFeatures.includes(feature.key)}
                    disabled={loading || update.isPending || !moduleEnabled}
                    onChange={(event) => toggleFeature(feature.key, event.target.checked)}
                  />
                  <span>{feature.label}</span>
                </label>
              ))}
            </fieldset>
          );
        })}
      </div>
    </div></SettingsRow>
  );
}