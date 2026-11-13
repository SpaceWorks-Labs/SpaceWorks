// "My cards" (/member/cards): every live card of this account. Each shows the ticket view
// (the QR to show at the desk) or the printed card, plus downloads, email and settings.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { CenteredCardLayout } from "../../../components/layouts";
import { Badge, EmptyState, ErrorText, SegmentedControl } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { PageHelp } from "../../help/PageHelp";
import { MemberAuthPanel } from "../MemberAuthPanel";
import { CardHolderSettings } from "./CardHolderSettings";
import { HolographicCard } from "./HolographicCard";
import { downloadMyCard, useEmailMyCard, useMemberIdentity, useMyCards, useWalletPass, type MyCard } from "./api";

const STATUS = { valid: { label: t`Valid`, tone: "success" }, expired: { label: t`Expired`, tone: "warn" },
  revoked: { label: t`Revoked`, tone: "danger" } } as const;
const WALLET_LABELS: Record<string, string> = { apple: t`Add to Apple Wallet`, google: t`Save to Google Wallet` };

export function WalletPage() {
  const { restoring, identity } = useMemberIdentity();
  const cards = useMyCards(!restoring && Boolean(identity.data?.id));
  const status = identity.error instanceof StructuredApiError ? identity.error.status : undefined;
  if (status === 401) return <MemberAuthPanel onAuthenticated={() => { void identity.refetch(); }} />;
  const rows = cards.data ?? [];
  return <CenteredCardLayout width="wide" title={t`My cards`} body={t`Your member, programme and event cards in one place.`}
    state={restoring || identity.isLoading || cards.isLoading ? { status: "loading" } : { status: "ready" }}
    primary={{ label: t`Back to my account`, href: "/member/account" }}
    footer={<PageHelp article="member/member-card" topic="your cards" className="flex justify-center" />}
    content={<div className="grid gap-6">
      {cards.error ? <ErrorText message={cards.error.message} onRetry={() => void cards.refetch()} /> : null}
      {cards.data && !rows.length ? <EmptyState message={t`No cards yet. A card appears here once a space, programme or event issues one to you.`} /> : null}
      {rows.map((card) => <CardEntry key={`${card.kind}-${card.id}`} card={card} />)}
    </div>} />;
}

function CardEntry({ card }: { card: MyCard }) {
  const [view, setView] = useState<"ticket" | "printed">("ticket");
  const [settings, setSettings] = useState(false);
  const email = useEmailMyCard();
  const wallet = useWalletPass(card);
  const live = card.status !== "revoked";
  return <section className="grid gap-3 rounded-card border border-line bg-panel p-4" aria-label={`${card.title}, ${card.issuer}`}>
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><p className="text-xs font-semibold uppercase text-muted">{card.issuer}</p>
        <h2 className="text-lg font-semibold text-ink">{card.title}</h2></div>
      <Badge tone={STATUS[card.status].tone}>{STATUS[card.status].label}</Badge>
    </div>
    {card.status === "revoked" ? <p role="status" className="rounded-control border border-danger-line p-3 text-sm text-danger">
      {t`This card was revoked. Ask staff for a new one.`}</p> : null}
    {card.status === "expired" ? <p role="status" className="rounded-control border border-warn p-3 text-sm text-warn-ink">
      {t`This card has expired. Renew your membership or ask the organiser.`}</p> : null}
    {card.photo_request_open ? <p role="status" className="text-sm text-warn-ink">{t`Staff asked for a new photo. Your card stays valid meanwhile.`}</p> : null}
    {live ? <SegmentedControl label={t`Card view`} value={view} onChange={(value) => setView(value as "ticket" | "printed")}
      options={[{ value: "ticket", label: t`Ticket` }, { value: "printed", label: t`Printed card` }]} /> : null}
    {live && view === "ticket" ? <TicketView card={card} /> : null}
    {live && view === "printed" ? <HolographicCard card={card} /> : null}
    {live ? <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button min-h-11" onClick={() => void downloadMyCard(card, "pdf")}>{t`Download PDF`}</button>
      <button type="button" className="desk-button-ghost min-h-11" onClick={() => void downloadMyCard(card, "png")}>{t`Download PNG`}</button>
      {card.check_url ? <a className="desk-button-ghost min-h-11" href={card.check_url} target="_blank" rel="noreferrer">{t`Check page`}</a> : null}
      {card.email_available ? <button type="button" className="desk-button-ghost min-h-11" disabled={email.isPending || email.isSuccess}
        onClick={() => email.mutate({ card })}>{email.isSuccess ? t`Emailed` : t`Email me my card`}</button> : null}
      {card.wallet_platforms.map((platform) => <button key={platform} type="button" className="desk-button-ghost min-h-11"
        disabled={wallet.isPending} onClick={() => wallet.mutate(platform)}>{WALLET_LABELS[platform] ?? platform}</button>)}
      {card.kind !== "staff_card" ? <button type="button" className="desk-button-ghost min-h-11" aria-expanded={settings} onClick={() => setSettings((value) => !value)}>
        {t`Card settings`}</button> : null}
    </div> : null}
    {email.error || wallet.error ? <ErrorText message={(email.error ?? wallet.error)?.message} /> : null}
    {settings && live && card.kind !== "staff_card" ? <CardHolderSettings card={card} /> : null}
  </section>;
}

function TicketView({ card }: { card: MyCard }) {
  const facts = [["Number", card.number], ["Valid until", card.valid_until || "No end date"], ["Type", card.label]].filter(([, value]) => value);
  return <div className="grid gap-3 rounded-control border border-line sm:grid-cols-[1fr_auto]">
    <div className="grid gap-3 p-4">
      <p className="text-xl font-semibold text-ink">{card.name}</p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        {facts.map(([label, value]) => <div key={label}><dt className="text-xs uppercase text-muted">{label}</dt>
          <dd className="font-semibold tabular-nums text-ink">{value}</dd></div>)}
      </dl>
    </div>
    {card.qr_image ? <div className="grid justify-items-center gap-2 border-t border-dashed border-line p-4 sm:border-l sm:border-t-0">
      <img src={card.qr_image} alt={card.kind === "member_card" ? t`Desk QR code` : t`Card check QR code`} className="h-40 w-40 rounded-control bg-white p-2" />
      <p className="max-w-[12rem] text-center text-xs text-muted">{card.kind === "member_card"
        ? t`Show this at the desk. It only holds a private member link.` : t`Anyone can scan this to check the card is valid.`}</p>
    </div> : null}
  </div>;
}
