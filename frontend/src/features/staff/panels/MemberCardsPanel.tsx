import { plural, t } from "@lingui/core/macro";
import { useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ErrorBlock, SegmentedControl } from "../../../components/ui";
import { featureEnabled } from "../../../lib/features";
import { CardJobList, JOB_LABELS, useStartCardJob, type CardJobKind } from "../../cards/cardJobs";
import { SheetPreviewDialog } from "../../cards/SheetPreviewDialog";
import { ProgrammesTab } from "../../organizations/idProgrammes/ProgrammesTab";
import { opsQueryState, useOpsTabs } from "../opsPresentation";
import { useMemberCards, useCardMemberships, usePrintCard, usePrintSheet } from "./memberCards/api";
import { memberCardJobsPath, useMemberCardSettings } from "./memberCards/apiCards";
import { BulkFromFilter } from "./memberCards/BulkFromFilter";
import { CardsTable } from "./memberCards/CardsTable";
import { useCardRowActions } from "./memberCards/CardsRowDialogs";
import { DesignTab } from "./memberCards/DesignTab";
import { IssueRoster } from "./memberCards/IssueRoster";
import { ScanCardBox } from "./memberCards/ScanCardBox";
import { SettingsTab } from "./memberCards/SettingsTab";
import type { CardStatus } from "./memberCards/types";
import { StaffCardsTab } from "./staffCards/StaffCardsTab";

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
  const [previewing, setPreviewing] = useState(false);
  const cards = useMemberCards(makerspaceId, status);
  const activeCards = useMemberCards(makerspaceId, "active");
  const settings = useMemberCardSettings(makerspaceId);
  const printCard = usePrintCard();
  const printSheet = usePrintSheet(makerspaceId);
  const jobsPath = memberCardJobsPath(makerspaceId);
  const startJob = useStartCardJob(jobsPath);
  const deskPrintOn = featureEnabled(enabledFeatures, "membership.card_desk_print");
  const row = useCardRowActions(makerspaceId, Boolean(settings.data?.email_available), deskPrintOn);
  const programmesOn = featureEnabled(enabledFeatures, "membership.id_programmes");
  const staffOn = featureEnabled(enabledFeatures, "membership.staff_cards");

  const rows = cards.data?.results ?? [];
  const cardedMembershipIds = (activeCards.data?.results ?? [])
    .map((card) => card.membership_id)
    .filter((id): id is number => id !== null);
  const printError = printCard.error ?? printSheet.error ?? startJob.error;
  const withoutCard = memberships.data && activeCards.data ? memberships.data.filter(item => !cardedMembershipIds.includes(item.id)).length : "—";
  const tabs = useOpsTabs("cardsTab", [
    { key: "cards", label: t`Cards`, count: cards.data?.count },
    { key: "issue", label: t`Issue` }, { key: "scan", label: t`Scan` }, { key: "bulk", label: t`Bulk` }, { key: "design", label: t`Card design` },
    ...(staffOn ? [{ key: "staff", label: t`Staff cards` }] : []),
    { key: "settings", label: t`Settings` }, ...(programmesOn ? [{ key: "programmes", label: t`ID programmes` }] : []),
  ], "cards");
  // Bulk outputs run as server jobs; a selection narrows them, otherwise every active card.
  const scope = { status: "active" as const, ...(selected.length ? { card_ids: selected } : {}) };
  // A print sheet is previewed first (paper, order, the first sheet); the dialog queues the job.
  const bulk = (kind: CardJobKind) => ({ label: kind === "bulk_sheet" ? `${JOB_LABELS[kind]}…` : JOB_LABELS[kind],
    onClick: () => (kind === "bulk_sheet" ? setPreviewing(true) : startJob.mutate({ kind, ...scope })) });

  if (tabs.active === "design" || tabs.active === "settings" || tabs.active === "programmes" || (tabs.active === "staff" && staffOn)) {
    return <div onClickCapture={tabs.onClickCapture}>
      <ListLayout width={tabs.active === "design" ? "wide" : "default"} header={{ title: t`Member cards` }}
        tabs={tabs.tabs} activeTab={tabs.active} state={{ status: "ready" }} isEmpty={false} empty={{ message: "" }}
        body={{ kind: "rows", rows: tabs.active === "design" ? <DesignTab makerspaceId={makerspaceId} numberingOn={featureEnabled(enabledFeatures, "membership.card_numbering")} />
          : tabs.active === "staff" ? <StaffCardsTab makerspaceId={makerspaceId} deskPrint={deskPrintOn} />
          : tabs.active === "settings" ? <SettingsTab makerspaceId={makerspaceId} /> : <ProgrammesTab makerspaceId={makerspaceId}
            sheetImport={featureEnabled(enabledFeatures, "membership.id_programmes_import_sheets")} /> }} />
    </div>;
  }
  return <div onClickCapture={tabs.onClickCapture}>
    <ListLayout header={{ title: t`Member cards`, subtitle: t`Cards that open the member area at the desk and prove membership.`,
      primary: { label: selected.length ? plural(selected.length, { one: "Print sheet (# selected)", other: "Print sheet (# selected)" }) : t`Print all active`,
        onClick: () => printSheet.mutate(selected), pending: printSheet.isPending, pendingLabel: t`Preparing…` },
      secondary: { label: t`All cards`, menu: [bulk("bulk_sheet"), bulk("zip"),
        ...(settings.data?.email_available ? [bulk("email")] : [])] } }}
      tabs={tabs.tabs} activeTab={tabs.active} stats={[{ label: t`Active cards on this page`, value: activeCards.data?.results.length ?? 0 },
        { label: t`Members without a card`, value: withoutCard, href: tabs.href("issue") }]}
      state={tabs.active === "cards" ? opsQueryState(cards, "member cards") : { status: "ready" }}
      isEmpty={tabs.active === "cards" && rows.length === 0}
      empty={{ message: status === "active" ? t`No cards yet. Issue one from the Issue tab.` : t`No revoked cards.`,
        action: status === "active" ? { label: t`Issue a card`, onClick: () => tabs.select("issue") } : undefined }}
      filters={tabs.active === "cards" ? { views: <SegmentedControl label={t`Card status`} value={status}
        options={[{ value: "active", label: t`Active` }, { value: "revoked", label: t`Revoked` }]}
        onChange={value => { setStatus(value as CardStatus); setSelected([]); }} /> } : undefined}
      body={tabs.active === "cards" ? { kind: "table", table: <>
        <CardJobList listPath={jobsPath} />
        <CardsTable cards={rows} status={status} loading={cards.isLoading} selectedIds={selected}
          onSelectionChange={setSelected} printingCardId={printCard.isPending ? (printCard.variables?.id ?? null) : null}
          onPrint={(card) => printCard.mutate(card)} onReissue={row.onReissue} onRevoke={row.onRevoke} rowActions={row.rowActions} />
        </> } : { kind: "rows", rows: tabs.active === "scan" ? <ScanCardBox makerspaceId={makerspaceId} />
          : tabs.active === "bulk" ? <div className="grid gap-3"><BulkFromFilter makerspaceId={makerspaceId} /><CardJobList listPath={jobsPath} /></div>
          : <IssueRoster makerspaceId={makerspaceId} cardedMembershipIds={cardedMembershipIds} memberships={memberships} names={issueNames} setNames={setIssueNames} /> }}
      detail={<>{printError ? <ErrorBlock error={printError} /> : null}{row.dialogs}
        <SheetPreviewDialog open={previewing} onClose={() => setPreviewing(false)} filter={scope} jobsPath={jobsPath}
          previewPath={`${jobsPath}/preview`} title={selected.length ? t`Print sheet: ${selected.length} selected cards` : t`Print sheet: all active cards`} /></>} />
  </div>;
}
