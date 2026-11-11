import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { Tabs } from "../../components/ui";
import { capabilityOn } from "../../lib/features";
import { ScreenHelp } from "../help/HelpLink";
import { StructuredApiError } from "../../lib/api";
import { FinanceOverview } from "./FinanceOverview";
import { LedgerEntriesSection } from "./LedgerEntriesSection";
import { MoneyQueues } from "./MoneyQueues";
import { OpeningBalances } from "./OpeningBalances";
import { FlagsSection, DisputesSection } from "./FlagsDisputes";
import { EventMoneySection } from "./EventMoneySection";
import { CashInHand } from "./CashInHand";
import { CollectionSheet } from "./CollectionSheet";
import { financeApi, financeKeys } from "./financeApi";
import { useRoutedSubTab } from "../staff/useRoutedSubTab";
import { AreaOverview } from "../staff/areaOverview/AreaOverview";

type Space = { id: number; name?: string; enabled_modules?: string[]; enabled_features?: string[] };

/**
 * The space's finance ledger (#94/#100). The server narrows every list to the caller's
 * areas; this panel only decides which sections to offer from the space's switches and
 * the caller's finance access. A section whose switch is off is not offered at all.
 */
export function FinancePanel({ makerspace, canViewFinance, canRecordPayment }: {
  makerspace: Space; canViewFinance: boolean; canRecordPayment: boolean;
}) {
  const ledgerOn = capabilityOn(makerspace, "finance.ledger");
  const access = useQuery({ queryKey: financeKeys.access(makerspace.id), queryFn: () => financeApi.access(makerspace.id),
    enabled: ledgerOn, retry: false });
  const sections = [
    // Decision 241: each area's money grouped by area (machines: type, then machine), with what is owed.
    ...(ledgerOn && access.data ? [{ key: "overview", label: t`Income and spending` }, { key: "areas", label: t`By area` },
      { key: "entries", label: t`Expenses and receipts` }] : []),
    ...(ledgerOn && access.data?.everything ? [{ key: "opening", label: t`Opening balances` }] : []),
    ...(ledgerOn && access.data && (access.data.everything || access.data.domains.includes("events"))
      ? [{ key: "events", label: t`Event money` }] : []),
    ...(canRecordPayment && (capabilityOn(makerspace, "billing.offline_claims") || capabilityOn(makerspace, "billing.maker_checker"))
      ? [{ key: "queues", label: t`Offline payments` }] : []),
    ...(canViewFinance && capabilityOn(makerspace, "billing.capture_flags") ? [{ key: "flags", label: t`Unexpected payments` }] : []),
    ...(canViewFinance && capabilityOn(makerspace, "billing.disputes") ? [{ key: "disputes", label: t`Disputes` }] : []),
    // Parity O-B3: many offline payments in one sheet, and the cash each collector still holds.
    ...(canRecordPayment && capabilityOn(makerspace, "billing.collection_sheet") ? [{ key: "collection", label: t`Collection sheet` }] : []),
    ...(canViewFinance && (makerspace.enabled_modules ?? []).includes("reports") ? [{ key: "cash", label: t`Cash in hand` }] : []),
    // Decision 242(m): gifts and sponsors have their own Donations area (staff tab `donations`).
  ];
  // 0.12.0 row 15: the section is the URL's last segment (`/admin/finance/disputes`). A section
  // that appears only once the access check settles still opens from its link.
  const route = useRoutedSubTab();
  const active = sections.some(section => section.key === route.segment) ? route.segment : sections[0]?.key;
  const denied = access.error instanceof StructuredApiError && access.error.status === 404;
  return <section className="grid min-w-0 gap-4" aria-labelledby="finance-heading">
    <header className="grid gap-1">
      <h2 id="finance-heading" className="title-page">{t`Finance`}</h2>
      <p className="text-sm text-muted">{t`Every amount `}{makerspace.name ?? t`your makerspace`} {t` took in or paid out, by month and area. Nothing here moves money by itself.`}</p>
    </header>
    {access.isLoading && ledgerOn ? <p role="status" className="text-sm text-muted">{t`Loading finance…`}</p> : null}
    {!sections.length && !access.isLoading
      ? <p className="rounded-lg border border-line bg-panel p-4 text-sm text-muted">{denied
        ? t`Finance shows the money for the areas you manage. You don't manage one in this space.`
        : t`No finance screens are switched on for this space. A Space Manager turns them on under Features.`}</p> : null}
    {sections.length ? <Tabs tabs={sections} activeKey={active ?? ""} label={t`Finance sections`} onChange={route.select} /> : null}
    {active ? <ScreenHelp screen={`finance.${active}`} /> : null}
    {active === "overview" && access.data ? <FinanceOverview makerspaceId={makerspace.id} /> : null}
    {active === "areas" && access.data ? <AreaOverview makerspaceId={makerspace.id} section="finance" /> : null}
    {active === "entries" && access.data ? <LedgerEntriesSection makerspaceId={makerspace.id} access={access.data} /> : null}
    {active === "opening" && access.data ? <OpeningBalances makerspaceId={makerspace.id} access={access.data} /> : null}
    {active === "events" && access.data ? <EventMoneySection makerspaceId={makerspace.id} access={access.data} /> : null}
    {active === "queues" ? <MoneyQueues makerspaceId={makerspace.id}
      claimsOn={capabilityOn(makerspace, "billing.offline_claims")} /> : null}
    {active === "flags" ? <FlagsSection makerspaceId={makerspace.id} /> : null}
    {active === "disputes" ? <DisputesSection makerspaceId={makerspace.id} /> : null}
    {active === "collection" ? <CollectionSheet makerspaceId={makerspace.id} makerChecker={capabilityOn(makerspace, "billing.maker_checker")} /> : null}
    {active === "cash" ? <CashInHand makerspaceId={makerspace.id}
      canHandover={canRecordPayment && capabilityOn(makerspace, "billing.collection_sheet")} /> : null}
  </section>;
}
