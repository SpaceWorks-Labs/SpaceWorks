import { t } from "@lingui/core/macro";
import { SettingsRow } from "../../../components/ui";
import { capabilityOn } from "../../../lib/features";
import type { ItemForm } from "./InventoryPanelShared";
import type { Makerspace } from "./shared";

export type LendingFlagSpace = Pick<Makerspace, "enabled_modules" | "enabled_features">;

/** The lane L12 item switches: a consumable is logged as used and never lent; expected-back shows on the public page. */
export function InventoryLendingFlags({ form, setForm, makerspace }: {
  form: ItemForm; setForm: (updater: (current: ItemForm) => ItemForm) => void; makerspace?: LendingFlagSpace;
}) {
  const consumables = capabilityOn(makerspace, "inventory.consumables") && form.tracking_mode === "quantity";
  const expectedBack = capabilityOn(makerspace, "inventory.expected_back");
  if (!consumables && !expectedBack) return null;
  return <SettingsRow label={t`Use and return`} helper="How this item is used up or when it is expected back."><div className="grid gap-2">
    {consumables ? <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={Boolean(form.is_consumable)}
      onChange={event => setForm(current => ({ ...current, is_consumable: event.target.checked }))} />{t`Consumable (logged as used, never lent)`}</label> : null}
    {expectedBack ? <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={Boolean(form.public_show_expected_back)}
      onChange={event => setForm(current => ({ ...current, public_show_expected_back: event.target.checked }))} />{t`Show expected-back date on the public page`}</label> : null}
  </div></SettingsRow>;
}
