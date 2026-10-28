import { toast } from "../../components/ui/toastStore";
import { SettingsRow } from "../../components/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { FEATURE_DEFINITIONS, isSecurityFeature } from "../../lib/features";
import type { Makerspace } from "./panels/shared";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

// Parentless features (parent_module === null) group under GENERAL: always available,
// never gated by a module.
const GENERAL = "__general__";

const MODULE_FEATURES = Object.entries(
  FEATURE_DEFINITIONS.filter(feature => !isSecurityFeature(feature.key)).reduce<Record<string, typeof FEATURE_DEFINITIONS>>((groups, feature) => {
    const group = feature.parent_module ?? GENERAL;
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
    })(); toast(next.length ? "Features updated." : "All features turned off.", { undo: async () => { await ((next: string[]) =>
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
    <SettingsRow label="Feature settings" helper="Modules are set by the platform administrator. Enable the available sub-features for this makerspace."><div className="@container grid min-w-0 gap-4">
      <div className="grid min-w-0 gap-2">


        <div className="flex flex-wrap gap-2">
          {enabledModules.map((module) => <Badge label="" key={module} tone="neutral">{module}</Badge>)}
        </div>
        {update.error ? <p className="text-sm text-danger" role="alert">{update.error.message}</p> : null}
      </div>
      <div className="mt-4 grid gap-3">
        {MODULE_FEATURES.map(([module, features]) => {
          const isGeneral = module === GENERAL;
          const moduleEnabled = isGeneral || enabledModules.includes(module);
          return (
            <fieldset key={module} className="grid gap-2 rounded border border-line p-3">
              <legend className="px-1 text-sm font-semibold text-ink">{isGeneral ? "General" : module}</legend>
              {!moduleEnabled ? <p className="text-sm text-muted">Module disabled by the platform administrator.</p> : null}
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