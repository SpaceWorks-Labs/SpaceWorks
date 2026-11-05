import type { ReactNode } from "react";
import { Tag } from "lucide-react";

import type { ChargeDomain } from "../../../lib/charges";
import { useStaffChargesOn } from "../useStaffChargesOn";
import { useStaffPricingOn } from "./priceOverrideApi";

/** A static line beside a price field, shown only where price lists (`charges.pricing`) and the domain's charges (#184) are on. */
function PricingNote({ domain, makerspaceId, className = "", children }: { domain: ChargeDomain; makerspaceId?: number; className?: string; children: ReactNode }) {
  const chargesOn = useStaffChargesOn(domain, makerspaceId);
  if (useStaffPricingOn(makerspaceId) !== true || !chargesOn) return null;
  return <p role="note" className={`flex items-start gap-2 text-xs text-muted ${className}`}>
    <Tag aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />{children}
  </p>;
}

/** Event forms do not know their space id; any staff space with price lists shows it. */
export function EventPriceNote({ makerspaceId, settings = false }: { makerspaceId?: number; settings?: boolean }) {
  return <PricingNote domain="events" makerspaceId={makerspaceId} className={settings ? "py-3" : "sm:col-span-2"}>
    Your space's default event price only prefills new events; this event keeps its own price.
  </PricingNote>;
}

export function PlanPriceNote({ makerspaceId }: { makerspaceId: number }) {
  return <PricingNote domain="membership" makerspaceId={makerspaceId} className="mb-3">
    Plan prices are set here; member discounts are in Settings &gt; Pricing.
  </PricingNote>;
}
