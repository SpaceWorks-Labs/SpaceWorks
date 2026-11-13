import { t } from "@lingui/core/macro";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { SettingsLayout, type SettingsLayoutSection } from "../../components/layouts";
import { staffRequest } from "../../lib/api";
import { useStaffGet, type Makerspace } from "./panels/shared";
import { adminQueryState } from "./adminPresentation";
import { DeploymentModules, type ModulesResponse } from "./ModuleSettingsRows";
import { ModulesBody } from "./modules/ModulesBody";
import { buildAreas } from "./modules/moduleModel";
import { useModuleSwitches } from "./modules/useModuleSwitches";
import { listSpaceRoles } from "./panels/staffRoles/staffRolesApi";

export function ModulesPanel({ makerspaceId }: { makerspaceId: number }) {
  const modules = useStaffGet<ModulesResponse>(["modules", makerspaceId], `/admin/makerspace/${makerspaceId}/modules`);
  const settings = useQuery({ queryKey: ["makerspace-settings", makerspaceId], queryFn: () => staffRequest<Makerspace>(`/admin/makerspaces/${makerspaceId}`) });
  const roles = useQuery({ queryKey: ["staff", "roles", makerspaceId], queryFn: () => listSpaceRoles(makerspaceId), retry: false });
  const switches = useModuleSwitches(makerspaceId);
  const groups = modules.data?.groups;
  const locks = modules.data?.feature_locks;
  const requirements = modules.data?.feature_requirements;
  const areas = useMemo(() => buildAreas(groups ?? [], settings.data?.enabled_features ?? [], locks ?? {}, requirements ?? {}),
    [groups, settings.data?.enabled_features, locks, requirements]);
  const sections: SettingsLayoutSection[] = [
    { id: "modules", rows: <ModulesBody areas={areas} roles={roles.data ?? []} switches={switches} /> },
    { id: "data-kept", title: t`When you switch something off`, rows: <div className="grid gap-2 text-sm text-muted">
      <p>{t`Nothing is deleted. Switch it back on and everything returns. Deleting an area's data is a separate, explicit step that only the platform administrator can take.`}</p>
      {modules.data?.capability_purge_url ? <a className="w-fit font-semibold text-ink underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" href={modules.data.capability_purge_url}>{t`Open this space's capability purge`}</a> : null}
    </div> },
    ...(modules.data?.deployment ? [{ id: "deployment", title: t`Deployment`, rows: <DeploymentModules deployment={modules.data.deployment} /> }] : []),
  ];
  return <SettingsLayout header={{ title: t`Areas & add-ons`, subtitle: t`Turn whole areas (Inventory, Machines, Events, Bookings, Shop) and add-ons (SMS, chat apps, analytics) on or off for this space, with the features inside each. Group them by area or by the role that uses them.` }}
    state={adminQueryState(modules, "modules")} isEmpty={!groups || groups.length === 0}
    empty={{ message: t`Nothing to switch on yet. Ask whoever runs your server to check its configuration.` }}
    sections={sections} />;
}
