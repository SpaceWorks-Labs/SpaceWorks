import { t } from "@lingui/core/macro";
import { useContext } from "react";

import { SettingsRow, StatusPill } from "../../../components/ui";
import { capabilityOn } from "../../../lib/features";
import { StaffListContext } from "../StaffListContext";
import type { SettingsDomain } from "../domainSettingsApi";
import { PricingDomainCard } from "../pricing/PricingDomainCard";

/** Settings domain -> the `charges.<key>` switch and the rate card's pricing domain (none for the shop). */
const AREA_MONEY: Record<SettingsDomain, { charges: string; pricing: string | null }> = {
  inventory: { charges: "loans", pricing: "loans" },
  machines: { charges: "machines", pricing: "machines" },
  bookings: { charges: "bookings", pricing: "bookings" },
  events: { charges: "events", pricing: "events" },
  shop: { charges: "shop", pricing: null },
};

/**
 * Decision 242(d): the area's money inside the area. A read-only "Charging on/off" line (the Space
 * Manager's `charges.*` switch, mirroring `charge_tracking_enabled`) and the area's rate card. The card
 * is editable only when the Space Manager delegated pricing; `PricingDomainCard` already renders the
 * server's `editable`/`locked`/`refusal` states, so nothing is unlocked here.
 */
export function AreaPricingSection({ makerspaceId, domain }: { makerspaceId: number; domain: SettingsDomain }) {
  const { makerspace } = useContext(StaffListContext);
  const money = AREA_MONEY[domain];
  if (!makerspace || makerspace.id !== makerspaceId || makerspace.enabled_features === undefined) return null;
  const charging = capabilityOn(makerspace, "charges.enabled") && capabilityOn(makerspace, `charges.${money.charges}`);
  const priceLists = capabilityOn(makerspace, "charges.pricing");
  return <SettingsRow label={t`Prices`} helper={t`What this area charges. Only the Space Manager, or someone they hand pricing to, can change it.`}>
    <div className="grid min-w-0 gap-3">
      <p className="flex flex-wrap items-center gap-2 text-sm text-ink">
        <span>{t`Charging`}</span>
        <StatusPill label={charging ? t`On` : t`Off`} tone={charging ? "success" : "neutral"} />
        <span className="text-muted">{t`(Space Manager setting)`}</span>
      </p>
      {!charging ? <p className="text-sm text-muted">{t`Nothing new is charged here. Charges raised before it was turned off still need settling.`}</p> : null}
      {money.pricing === null ? <p className="text-sm text-muted">{t`Each shop item has its own price, set in the catalogue.`}</p>
        : priceLists ? <PricingDomainCard makerspaceId={makerspaceId} domain={money.pricing} />
        : <p className="text-sm text-muted">{t`Price lists are off in this space. The Space Manager can turn them on.`}</p>}
    </div>
  </SettingsRow>;
}
