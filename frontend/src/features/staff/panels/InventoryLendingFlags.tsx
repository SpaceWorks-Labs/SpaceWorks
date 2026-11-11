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
  // Event-only lending needs the events module; a consumable is never lent at all. An item already
  // flagged keeps the box while Events is off, so staff can clear a flag that now blocks all lending.
  const eventOnly = (Boolean(makerspace?.enabled_modules?.includes("events")) || Boolean(form.event_only)) && !form.is_consumable;
  if (!consumables && !expectedBack && !eventOnly) return null;
  return <SettingsRow label={t`Use and return`} helper={t`How this item is used up or when it is expected back.`}><div className="grid gap-2">
    {consumables ? <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={Boolean(form.is_consumable)}
      onChange={event => setForm(current => ({ ...current, is_consumable: event.target.checked }))} />{t`Consumable (logged as used, never lent)`}</label> : null}
    {expectedBack ? <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={Boolean(form.public_show_expected_back)}
      onChange={event => setForm(current => ({ ...current, public_show_expected_back: event.target.checked }))} />{t`Show expected-back date on the public page`}</label> : null}
    {eventOnly ? <label className="inline-flex min-h-11 items-center gap-2"><input type="checkbox" checked={Boolean(form.event_only)}
      onChange={event => setForm(current => ({ ...current, event_only: event.target.checked }))} />
      <span>{t`Lend only at events`}<span className="block text-sm text-muted">{t`Only event organizers can request it for participants. Ordinary requests, self-checkout and direct handouts refuse it.`}</span></span></label> : null}
  </div></SettingsRow>;
}
