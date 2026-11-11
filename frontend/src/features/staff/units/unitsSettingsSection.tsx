import { t } from "@lingui/core/macro";
import type { SettingsLayoutSection } from "../../../components/layouts";
import { capabilityOn } from "../../../lib/features";
import { UnitSwitchesSettings, UNITS_SWITCH } from "./UnitSwitchesSettings";
import { UnitsSettings } from "./UnitsSettings";

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/**
 * Settings › People › Member units (parity O-F1): the two switches, then, while units are on, the
 * tree editor itself. Present for the Space Manager whenever the membership module is installed, so
 * the switch can be turned on here; the editor is absent while the switch is off (#183B).
 */
export function unitsSettingsSections(space: Space, canManageMakerspace: boolean): SettingsLayoutSection[] {
  if (!canManageMakerspace || !(space.enabled_modules ?? []).includes("membership")) return [];
  return [{ id: "units", title: t`Member units`,
    description: t`Districts, chapters or branches inside this space, and staff who work with one unit only.`,
    rows: <>
      <UnitSwitchesSettings key={`switches-${space.id}`} space={space} />
      {capabilityOn(space, UNITS_SWITCH) ? <div className="pt-4"><UnitsSettings key={space.id} makerspaceId={space.id} canManage /></div> : null}
    </> }];
}
