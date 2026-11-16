import { t } from "@lingui/core/macro";
import { BarChart3, CreditCard, LineChart, Store } from "lucide-react";
import type { CataloguePart } from "./types";

/** Payments, Shop and Reports groups. */
export const moneyAndReports = (): CataloguePart => ({
  payments: { icon: CreditCard, value: t`Money owed tracked; online checkout optional.`,
    what: t`Charges, receipts and offline settlement work without any provider. Turn on Stripe or Razorpay to take money online for bookings, events, machine jobs and plans.`,
    roles: [t`Space managers`, t`Finance staff`, t`Members`],
    
    
    
    integrations: [t`Stripe`, t`Razorpay`, t`Pay links`, t`Receipts as PDF`] },
  shop: { icon: Store, value: t`Sell consumables and merch from the same space.`,
    what: t`Products with sizes and stock, a public shop for pickup, a front-desk till and every sale in the same ledger.`,
    roles: [t`Shop staff`, t`Members`, t`Visitors`], 
    
    integrations: [t`Online payments`, t`Receipts`] },
  reports: { icon: BarChart3, value: t`Reports for every module, grouped like the module screens.`,
    what: t`One hub of reports grouped by module, with search, pinned favourites and role filtering. Each report exports, schedules by email and feeds the dashboards; the platform owner gets cross-space roll-ups.`,
    roles: [t`Space managers`, t`Every role, for the reports it may see`, t`Superadmins`],
    
    
    integrations: [t`CSV, XLSX and PDF`, t`Scheduled email`, t`Metabase`, t`Grafana`, t`API`],
    newIn: [t`Reports and analytics for every module`, t`A hub grouped by module with favourites`] },
  analytics: { icon: LineChart, value: t`Metabase and Grafana, scoped to your space.`,
    what: t`Optional dashboards that connect to read-only views of your own space's data. A dashboard can never see another space.`,
    roles: [t`Space managers`, t`Superadmins`], 
    integrations: [t`Metabase`, t`Grafana`] },
});
