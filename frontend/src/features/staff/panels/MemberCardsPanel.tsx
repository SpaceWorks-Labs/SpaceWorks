import { useState } from "react";

import { ListLayout } from "../../../components/layouts";
import { ErrorBlock, SegmentedControl } from "../../../components/ui";
import { opsQueryState, useOpsTabs } from "../opsPresentation";
import {
  useMemberCards,
  useCardMemberships,
  usePrintCard,
  usePrintSheet,
  useReissueCard,
  useRevokeCard,
} from "./memberCards/api";
import { CardsTable } from "./memberCards/CardsTable";
import { CardTemplateForm } from "./memberCards/CardTemplateForm";
import { ReissueCardDialog, RevokeCardDialog } from "./memberCards/CardDialogs";
import { IssueRoster } from "./memberCards/IssueRoster";
import { useCardTemplateDraft } from "./memberCards/useCardTemplateDraft";
import { ScanCardBox } from "./memberCards/ScanCardBox";
import type { CardStatus, MemberCard, ReissueReason } from "./memberCards/types";


/** Member ID cards: issue, print, reissue, revoke, plus the front-desk scan lookup.
 *
 *  Gated by the `membership` module in staffTabs.TAB_MODULES — a card belongs to a
 *  membership, so without that module every endpoint here 404s.
 */
export function MemberCardsPanel({ makerspaceId }: { makerspaceId: number }) {
  const [status, setStatus] = useState<CardStatus>("active");
  const [selected, setSelected] = useState<number[]>([]);
  const [reissueTarget, setReissueTarget] = useState<MemberCard | null>(null);
  const [reissueReason, setReissueReason] = useState<ReissueReason>("lost");
  const [revokeTarget, setRevokeTarget] = useState<MemberCard | null>(null);
  const [revokeReason, setRevokeReason] = useState("");

  const memberships = useCardMemberships(makerspaceId);
  const editor = useCardTemplateDraft(makerspaceId);
  const [issueNames, setIssueNames] = useState<Record<number, string>>({});
  const cards = useMemberCards(makerspaceId, status);
  const activeCards = useMemberCards(makerspaceId, "active");
  const printCard = usePrintCard();
  const printSheet = usePrintSheet(makerspaceId);
  const reissue = useReissueCard(makerspaceId);
  const revoke = useRevokeCard(makerspaceId);

  const rows = cards.data?.results ?? [];
  const cardedMembershipIds = (activeCards.data?.results ?? [])
    .map((card) => card.membership_id)
    .filter((id): id is number => id !== null);
  const printError = printCard.error ?? printSheet.error;
  const withoutCard = memberships.data && activeCards.data ? memberships.data.filter(row => !cardedMembershipIds.includes(row.id)).length : "—";
  const tabs = useOpsTabs("cardsTab", [
    { key: "cards", label: "Cards", count: cards.data?.count },
    { key: "issue", label: "Issue" }, { key: "scan", label: "Scan" }, { key: "layout", label: "Card layout" },
  ], "cards");

  if (tabs.active === "layout") return <div onClickCapture={tabs.onClickCapture}>
    <CardTemplateForm editor={editor} tabs={tabs.tabs} activeTab={tabs.active} />
  </div>;
  return <div onClickCapture={tabs.onClickCapture}>
    <ListLayout header={{ title: "Member cards", subtitle: "Printable cards that open the member area at the desk.",
      primary: { label: selected.length ? "Print sheet (" + selected.length + " selected)" : "Print all active",
        onClick: () => printSheet.mutate(selected), pending: printSheet.isPending, pendingLabel: "Preparing…" },
      secondary: { label: "Scan a card", onClick: () => tabs.select("scan") } }}
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
        <CardsTable
          cards={rows}
          status={status}
          loading={cards.isLoading}
          selectedIds={selected}
          onSelectionChange={setSelected}
          printingCardId={printCard.isPending ? (printCard.variables?.id ?? null) : null}
          onPrint={(card) => printCard.mutate(card)}
          onReissue={(card) => {
            setReissueReason("lost");
            setReissueTarget(card);
          }}
          onRevoke={(card) => {
            setRevokeReason("");
            setRevokeTarget(card);
          }}
        />


        </> } : { kind: "rows", rows: tabs.active === "scan" ? <ScanCardBox makerspaceId={makerspaceId} />
          : <IssueRoster makerspaceId={makerspaceId} cardedMembershipIds={cardedMembershipIds} memberships={memberships} names={issueNames} setNames={setIssueNames} /> }}
      detail={<>{printError ? <ErrorBlock error={printError} /> : null}
      <ReissueCardDialog
        card={reissueTarget}
        reason={reissueReason}
        pending={reissue.isPending}
        error={reissue.error instanceof Error ? reissue.error.message : undefined}
        onReasonChange={setReissueReason}
        onClose={() => setReissueTarget(null)}
        onSubmit={() => {
          if (!reissueTarget) return;
          reissue.mutate(
            { cardId: reissueTarget.id, reason: reissueReason },
            { onSuccess: () => setReissueTarget(null) },
          );
        }}
      />
      <RevokeCardDialog
        card={revokeTarget}
        reason={revokeReason}
        pending={revoke.isPending}
        error={revoke.error instanceof Error ? revoke.error.message : undefined}
        onReasonChange={setRevokeReason}
        onClose={() => setRevokeTarget(null)}
        onSubmit={() => {
          if (!revokeTarget) return;
          revoke.mutate(
            { cardId: revokeTarget.id, reason: revokeReason.trim() || undefined },
            { onSuccess: () => setRevokeTarget(null) },
          );
        }}
      />

      </>} />
  </div>;
}
