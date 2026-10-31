import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Tabs } from "../../../components/ui";
import { capabilityOn } from "../../../lib/features";
import { DiscountsPanel } from "./DiscountsPanel";
import { PricingCurrency } from "./PricingCurrency";
import { PricingDomainCard } from "./PricingDomainCard";
import { installedDomains, pricingApi, pricingKeys } from "./pricingApi";

type Space = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/** Settings > Pricing: the currency, one rate card per installed area, then member discounts. */
export function PricingSettings({ makerspace, canManageMakerspace }: { makerspace: Space; canManageMakerspace: boolean }) {
  const modules = makerspace.enabled_modules ?? [];
  const domains = installedDomains(modules);
  const [active, setActive] = useState<string>(domains[0]?.domain ?? "loans");
  const discountsOn = capabilityOn(makerspace, "charges.discounts");
  // The discount editor shows amounts in the space's currency (the same cached query the currency control reads).
  const currency = useQuery({ queryKey: pricingKeys.currency(makerspace.id), queryFn: () => pricingApi.currency(makerspace.id),
    retry: false, enabled: discountsOn });
  // Without finance access the currency endpoint 404s; the lending rate card (always installed) carries it too.
  const loansCard = useQuery({ queryKey: pricingKeys.card(makerspace.id, "loans"), queryFn: () => pricingApi.card(makerspace.id, "loans"),
    enabled: discountsOn && Boolean(currency.error) });
  const code = currency.data?.default_currency ?? loansCard.data?.currency ?? "";
  if (!capabilityOn(makerspace, "charges.pricing")) return null;
  return <div className="grid min-w-0 gap-6 py-5">
    <PricingCurrency makerspaceId={makerspace.id} canEdit={canManageMakerspace} />
    <Tabs label="Pricing areas" tabs={domains.map(entry => ({ key: entry.domain, label: entry.label }))} activeKey={active}
      onChange={setActive}>
      <PricingDomainCard key={active} makerspaceId={makerspace.id} domain={active} />
    </Tabs>
    {discountsOn ? <DiscountsPanel makerspaceId={makerspace.id}
      currency={code} domains={domains.map(entry => entry.domain)}
      membershipOn={modules.includes("membership")} canEdit={canManageMakerspace} /> : null}
  </div>;
}
