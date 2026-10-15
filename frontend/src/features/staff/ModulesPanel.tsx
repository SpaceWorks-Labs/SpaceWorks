import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SettingsLayout, type SettingsLayoutSection } from "../../components/layouts";
import { ErrorText } from "../../components/ui";
import { invalidateToastUndo, toast, toastSession } from "../../components/ui/toastStore";
import { StructuredApiError, staffRequest } from "../../lib/api";
import { useStaffGet } from "./panels/shared";
import { adminQueryState } from "./adminPresentation";
import { DeploymentModules, ModuleSettingsRow, type ModulesResponse } from "./ModuleSettingsRows";
import { PHONE_HIDES_SETTINGS_NAV, SettingsSectionJump } from "./SettingsSectionJump";

const errorText = (error: unknown) => error instanceof StructuredApiError
  ? error.detail ?? error.message : "Couldn't change this module. Try again.";

export function ModulesPanel({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [pendingModules, setPendingModules] = useState(new Set<string>());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const queryKey = ["modules", makerspaceId];
  const modules = useStaffGet<ModulesResponse>(queryKey, `/admin/makerspace/${makerspaceId}/modules`);
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey }),
      client.invalidateQueries({ queryKey: ["staff", "makerspaces"] }),
      client.invalidateQueries({ queryKey: ["report-catalog"] }),
      client.invalidateQueries({ queryKey: ["operations-report"] }),
    ]);
  };
  const changeModule = ({ key, action }: { key: string; action: "install" | "uninstall" }) =>
    staffRequest(`/admin/makerspace/${makerspaceId}/modules/${action}`, { method: "POST", body: JSON.stringify({ key }) });
  const change = useMutation({
    mutationFn: changeModule,
    onMutate: ({ key }) => {
      setPendingModules(current => new Set(current).add(key));
      setErrors(current => ({ ...current, [key]: "" }));
      invalidateToastUndo(`module:${makerspaceId}:${key}`);
      return toastSession();
    },
    onError: (error, { key }) => setErrors(current => ({ ...current, [key]: errorText(error) })),
    onSettled: (_data, _error, { key }) => setPendingModules(current => { const next = new Set(current); next.delete(key); return next; }),
    onSuccess: async (_data, { key, action }, session) => {
      await refresh();
      if (session !== toastSession()) return;
      const label = modules.data?.groups.flatMap(group => group.modules).find(module => module.key === key)?.label ?? key;
      toast(`${label} ${action === "install" ? "installed" : "uninstalled"}.`, {
        undoKey: `module:${makerspaceId}:${key}`,
        undo: async () => { await changeModule({ key, action: action === "install" ? "uninstall" : "install" }); await refresh(); },
      });
    },
  });
  const groups = modules.data?.groups ?? [];
  const sections: SettingsLayoutSection[] = [
    ...groups.map(group => ({ id: `modules-${group.key}`, title: `${group.label} · ${group.always_on ? "Always on" : `${group.installed_count} of ${group.module_count}`}`,
      description: group.description,
      rows: <>{group.modules.map(module => <div key={module.key} className="border-t border-line first:border-0">
        <ModuleSettingsRow module={module} pending={pendingModules.has(module.key)}
          onChange={action => change.mutate({ key: module.key, action })} />
        {errors[module.key] ? <ErrorText message={errors[module.key]} /> : null}
      </div>)}</> })),
    ...(modules.data?.deployment ? [{ id: "deployment", title: "Deployment", rows: <DeploymentModules deployment={modules.data.deployment} /> }] : []),
  ];
  return <div className={PHONE_HIDES_SETTINGS_NAV}><SettingsLayout header={{ title: "Modules", subtitle: "Switch feature families on for this space. Turning one off keeps its data; turning it back on restores everything. Delete data separately from the command line.",
    meta: <SettingsSectionJump sections={sections} /> }}
    state={adminQueryState(modules, "modules")} isEmpty={groups.length === 0}
    empty={{ message: "No modules are available yet. Check the deployment configuration." }}
    sections={sections} /></div>;
}
