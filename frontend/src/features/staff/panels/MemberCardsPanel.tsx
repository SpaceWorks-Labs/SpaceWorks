import { useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ErrorBlock, SegmentedControl } from "../../../components/ui";
import { featureEnabled } from "../../../lib/features";
import { CardJobList, JOB_LABELS, useStartCardJob, type CardJobKind } from "../../cards/cardJobs";
import { ProgrammesTab } from "../../organizations/idProgrammes/ProgrammesTab";
import { opsQueryState, useOpsTabs } from "../opsPresentation";
import { useMemberCards, useCardMemberships, usePrintCard, usePrintSheet } from "./memberCards/api";
import { memberCardJobsPath, useMemberCardSettings } from "./memberCards/apiCards";
import { CardsTable } from "./memberCards/CardsTable";
import { useCardRowActions } from "./memberCards/CardsRowDialogs";
import { DesignTab } from "./memberCards/DesignTab";
import { IssueRoster } from "./memberCards/IssueRoster";
import { ScanCardBox } from "./memberCards/ScanCardBox";
import { SettingsTab } from "./memberCards/SettingsTab";
import type { CardStatus } from "./memberCards/types";

/** Member ID cards: issue, print, download, email, bulk jobs, the door scan, the card
 *  design and settings, and (when switched on) the ID programmes this space hosts.
 *
 *  Gated by the `membership` module in staffTabs.TAB_MODULES — a card belongs to a
 *  membership, so without that module every endpoint here 404s.
 */
export function MemberCardsPanel({ makerspaceId, enabledFeatures = [] }: { makerspaceId: number; enabledFeatures?: string[] }) {
  const [status, setStatus] = useState<CardStatus>("active");
  const [selected, setSelected] = useState<number[]>([]);
  const memberships = useCardMemberships(makerspaceId);
  const [issueNames, setIssueNames] = useState<Record<number, string>>({});
  const cards = useMemberCards(makerspaceId, status);
  const activeCards = useMemberCards(makerspaceId, "active");
  const settings = useMemberCardSettings(makerspaceId);
  const printCard = usePrintCard();
  const printSheet = usePrintSheet(makerspaceId);
  const jobsPath = memberCardJobsPath(makerspaceId);
  const startJob = useStartCardJob(jobsPath);
  const row = useCardRowActions(makerspaceId, Boolean(settings.data?.email_available));
  const programmesOn = featureEnabled(enabledFeatures, "membership.id_programmes");

  const rows = cards.data?.results ?? [];
  const cardedMembershipIds = (activeCards.data?.results ?? [])
    .map((card) => card.membership_id)
    .filter((id): id is number => id !== null);
  const printError = printCard.error ?? printSheet.error ?? startJob.error;
  const withoutCard = memberships.data && activeCards.data ? memberships.data.filter(item => !cardedMembershipIds.includes(item.id)).length : "—";
  const tabs = useOpsTabs("cardsTab", [
    { key: "cards", label: "Cards", count: cards.data?.count },
    { key: "issue", label: "Issue" }, { key: "scan", label: "Scan" }, { key: "design", label: "Card design" },
    { key: "settings", label: "Settings" }, ...(programmesOn ? [{ key: "programmes", label: "ID programmes" }] : []),
  ], "cards");
  // Bulk outputs run as server jobs; a selection narrows them, otherwise every active card.
  const bulk = (kind: CardJobKind) => ({ label: JOB_LABELS[kind], onClick: () => startJob.mutate({
    kind, status: "active", ...(selected.length ? { card_ids: selected } : {}) }) });

  if (tabs.active === "design" || tabs.active === "settings" || tabs.active === "programmes") {
    return <div onClickCapture={tabs.onClickCapture}>
      <ListLayout width={tabs.active === "design" ? "wide" : "default"} header={{ title: "Member cards" }}
        tabs={tabs.tabs} activeTab={tabs.active} state={{ status: "ready" }} isEmpty={false} empty={{ message: "" }}
        body={{ kind: "rows", rows: tabs.active === "design" ? <DesignTab makerspaceId={makerspaceId} />
          : tabs.active === "settings" ? <SettingsTab makerspaceId={makerspaceId} /> : <ProgrammesTab makerspaceId={makerspaceId} /> }} />
    </div>;
  }
  return <div onClickCapture={tabs.onClickCapture}>
    <ListLayout header={{ title: "Member cards", subtitle: "Cards that open the member area at the desk and prove membership.",
      primary: { label: selected.length ? "Print sheet (" + selected.length + " selected)" : "Print all active",
        onClick: () => printSheet.mutate(selected), pending: printSheet.isPending, pendingLabel: "Preparing…" },
      secondary: { label: "All cards", menu: [bulk("bulk_sheet"), bulk("zip"),
        ...(settings.data?.email_available ? [bulk("email")] : [])] } }}
      tabs={tabs.tabs} activeTab={tabs.active} stats={[{ label: "Active cards on this page", value: activeCards.data?.results.length ?? 0 },
        { label: "Members without a card", value: withoutCard, href: tabs.href("issue") }]}
      state={tabs.active === "cards" ? opsQueryState(cards, "member cards") : { status: "ready" }}
      isEmpty={tabs.active === "cards" && rows.length === 0}
      empty={{ message: status === "active" ? "No cards yet. Issue one from the Issue tab." : "No revoked cards.",
        action: status === "active" ? { label: "Issue a card", onClick: () => tabs.select("issue") } : undefined }}
      filters={tabs.active === "cards" ? { views: <SegmentedControl label="Card status" value={status}
        options={[{ value: "active", label: "Active" }, { value: "revoked", label: "Revoked" }]}
        onChange={value => { setStatus(value as CardStatus); setSelected([]); }} /> } : undefined}
      body={tabs.active === "cards" ? { kind: "table", table: <>
        <CardJobList listPath={jobsPath} />
        <CardsTable cards={rows} status={status} loading={cards.isLoading} selectedIds={selected}
          onSelectionChange={setSelected} printingCardId={printCard.isPending ? (printCard.variables?.id ?? null) : null}
          onPrint={(card) => printCard.mutate(card)} onReissue={row.onReissue} onRevoke={row.onRevoke} rowActions={row.rowActions} />
        </> } : { kind: "rows", rows: tabs.active === "scan" ? <ScanCardBox makerspaceId={makerspaceId} />
          : <IssueRoster makerspaceId={makerspaceId} cardedMembershipIds={cardedMembershipIds} memberships={memberships} names={issueNames} setNames={setIssueNames} /> }}
      detail={<>{printError ? <ErrorBlock error={printError} /> : null}{row.dialogs}</>} />
  </div>;
}
