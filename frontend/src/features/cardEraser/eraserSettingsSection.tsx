import { t } from "@lingui/core/macro";

import type { SettingsLayoutSection } from "../../components/layouts";
import { capabilityOn } from "../../lib/features";
import { EraserProviderCard } from "./EraserProviderCard";

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/** Decision 314(c): Settings › Background eraser, for the Space Manager while `cards.photo_cutout` is on. */
export function eraserSettingsSections(space: Space, canManageMakerspace: boolean): SettingsLayoutSection[] {
  if (!canManageMakerspace || !capabilityOn(space, "cards.photo_cutout")) return [];
  return [{ id: "eraser", title: t`Background eraser`,
    rows: <EraserProviderCard key={space.id} scope={{ kind: "space", makerspaceId: space.id }} /> }];
}
