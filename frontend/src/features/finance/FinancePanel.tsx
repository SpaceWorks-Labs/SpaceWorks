import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Tabs } from "../../components/ui";
import { capabilityOn } from "../../lib/features";
import { ScreenHelp } from "../help/HelpLink";
import { StructuredApiError } from "../../lib/api";
import { FinanceOverview } from "./FinanceOverview";
import { LedgerEntriesSection } from "./LedgerEntriesSection";
import { MoneyQueues } from "./MoneyQueues";
import { FlagsSection, DisputesSection } from "./FlagsDisputes";
import { EventMoneySection } from "./EventMoneySection";
import { financeApi, financeKeys } from "./financeApi";
import { DonationsSection } from "../staff/sponsors/DonationsSection";
import { SponsorsSection } from "../staff/sponsors/SponsorsSection";

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
    ...(ledgerOn && access.data ? [{ key: "overview", label: t`Income and spending` }, { key: "entries", label: t`Expenses and receipts` }] : []),
    ...(ledgerOn && access.data && (access.data.everything || access.data.domains.includes("events"))
      ? [{ key: "events", label: t`Event money` }] : []),
    ...(canRecordPayment && (capabilityOn(makerspace, "billing.offline_claims") || capabilityOn(makerspace, "billing.maker_checker"))
      ? [{ key: "queues", label: t`Offline payments` }] : []),
    ...(canViewFinance && capabilityOn(makerspace, "billing.capture_flags") ? [{ key: "flags", label: t`Unexpected payments` }] : []),
    ...(canViewFinance && capabilityOn(makerspace, "billing.disputes") ? [{ key: "disputes", label: t`Disputes` }] : []),
    // Lane L18: gifts and sponsors are the ledger's `donations` domain, read by finance staff only.
    ...(canViewFinance && capabilityOn(makerspace, "finance.donations") ? [{ key: "donations", label: t`Donations` }] : []),
    ...(canViewFinance && capabilityOn(makerspace, "finance.sponsors") ? [{ key: "sponsors", label: t`Sponsors` }] : []),
  ];
  const [chosen, setChosen] = useState("overview");
  const active = sections.some(section => section.key === chosen) ? chosen : sections[0]?.key;
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
    {sections.length ? <Tabs tabs={sections} activeKey={active ?? ""} label={t`Finance sections`} onChange={setChosen} /> : null}
    {active ? <ScreenHelp screen={`finance.${active}`} /> : null}
    {active === "overview" && access.data ? <FinanceOverview makerspaceId={makerspace.id} /> : null}
    {active === "entries" && access.data ? <LedgerEntriesSection makerspaceId={makerspace.id} access={access.data} /> : null}
    {active === "events" && access.data ? <EventMoneySection makerspaceId={makerspace.id} access={access.data} /> : null}
    {active === "queues" ? <MoneyQueues makerspaceId={makerspace.id}
      claimsOn={capabilityOn(makerspace, "billing.offline_claims")} /> : null}
    {active === "flags" ? <FlagsSection makerspaceId={makerspace.id} /> : null}
    {active === "disputes" ? <DisputesSection makerspaceId={makerspace.id} /> : null}
    {active === "donations" ? <DonationsSection makerspace={makerspace} canRecordPayment={canRecordPayment} /> : null}
    {active === "sponsors" ? <SponsorsSection makerspaceId={makerspace.id} canRecordPayment={canRecordPayment} /> : null}
  </section>;
}
