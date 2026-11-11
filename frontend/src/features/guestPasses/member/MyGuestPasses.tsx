import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { StatusPill } from "../../../components/ui";
import { memberRequest } from "../../../lib/api";
import { PayNextStep } from "../../payments/PayNextStep";
import { guestErrorText, guestKeys, guestMemberApi, type HolderPass } from "../api";
import { entitlementSummary, passKindLabel, passStatusLabel, passStatusTone, passWindow } from "../labels";

const WALLET_LABELS: Record<string, string> = { apple: t`Add to Apple Wallet`, google: t`Save to Google Wallet` };

/**
 * The holder's own passes (decision 223): what each allows, the waiver step, wallet buttons and,
 * after enough visits, the invitation to join. Renders nothing for someone with no passes.
 */
export function MyGuestPasses({ makerspaceId, paymentsHref, joinSlot }: {
  makerspaceId: number; paymentsHref: string; joinSlot?: (passId: number) => ReactNode;
}) {
  const client = useQueryClient();
  const mine = useQuery({ queryKey: guestKeys.mine(makerspaceId), queryFn: () => guestMemberApi.mine(makerspaceId), retry: false });
  const accept = useMutation({
    mutationFn: (passId: number) => guestMemberApi.acceptWaiver(makerspaceId, passId),
    onSuccess: () => { void client.invalidateQueries({ queryKey: guestKeys.mine(makerspaceId) }); void client.invalidateQueries({ queryKey: ["presence"] }); },
  });
  const wallet = useMutation({
    mutationFn: ({ passId, platform }: { passId: number; platform: string }) => guestMemberApi.wallet(makerspaceId, passId, platform),
    // Apple's download link lives for a minute, so it opens straight away.
    onSuccess: (data) => { window.location.assign(data.url); },
  });
  if (mine.isLoading) return <p role="status" className="text-sm text-muted">{t`Loading your passes…`}</p>;
  if (mine.isError) return null; // Feature off (404) or signed out: the section simply isn't there.
  const passes = mine.data?.passes ?? [];
  if (!passes.length) return null;
  const latest = passes[0];
  return <section aria-labelledby="my-passes-title" className="desk-panel grid gap-4 p-5">
    <div><h2 id="my-passes-title" className="title-panel">{t`My passes`}</h2>
      <p className="mt-1 text-sm text-muted">{t`${mine.data?.visits_30d ?? 0} visits in the last 30 days.`}</p></div>
    <ul className="grid gap-3">
      {passes.map((pass) => <PassCard key={pass.id} pass={{ ...pass, makerspaceId }} paymentsHref={paymentsHref}
        accepting={accept.isPending && accept.variables === pass.id} onAccept={() => accept.mutate(pass.id)}
        walletPending={wallet.isPending} onWallet={(platform) => wallet.mutate({ passId: pass.id, platform })} />)}
    </ul>
    {accept.error || wallet.error ? <p role="alert" className="text-sm text-danger">{guestErrorText(accept.error ?? wallet.error)}</p> : null}
    {mine.data?.should_prompt_join ? <div className="grid gap-2 rounded-2xl border border-accent p-4">
      <p className="title-section">{t`Enjoying your visits?`}</p>
      <p className="text-sm text-muted">{t`You've visited ${mine.data.visits_30d} times recently. Become a member to keep coming without a pass.`}</p>
      {joinSlot ? joinSlot(latest.id) : null}
    </div> : null}
  </section>;
}

function PassCard({ pass, paymentsHref, accepting, onAccept, walletPending, onWallet }: {
  pass: HolderPass & { makerspaceId: number }; paymentsHref: string; accepting: boolean; onAccept: () => void; walletPending: boolean; onWallet: (platform: string) => void;
}) {
  const live = pass.status === "active" || pass.status === "issued";
  return <li className="grid gap-2 rounded-2xl border border-line p-4">
    <div className="flex flex-wrap items-center gap-2">
      <p className="title-section">{passKindLabel(pass.kind)}</p>
      <StatusPill tone={passStatusTone(pass.status)} label={passStatusLabel(pass.status)} />
    </div>
    <p className="text-sm text-muted">{passWindow(pass.valid_from, pass.valid_until)}{pass.sponsor_name ? ` · ${t`Guest of ${pass.sponsor_name}`}` : ""}</p>
    <p className="text-sm text-ink">{entitlementSummary(pass.entitlements)}</p>
    {live && pass.payment_status === "pending" ? <div role="status" className="text-sm text-warn-ink">{t`This day pass goes live once it is paid.`}<PayNextStep paymentsHref={paymentsHref} /></div> : null}
    {live && pass.waiver_required && !pass.waiver_accepted ? <WaiverStep makerspaceId={pass.makerspaceId} accepting={accepting} onAccept={onAccept} /> : null}
    {live && pass.waiver_accepted ? <p className="text-sm text-success-ink">{t`Waiver accepted.`}</p> : null}
    {live && pass.wallet_platforms?.length ? <div className="flex flex-wrap gap-2">
      {pass.wallet_platforms.map((platform) => <button key={platform} type="button" className="desk-button-ghost min-h-11" disabled={walletPending}
        onClick={() => onWallet(platform)}>{WALLET_LABELS[platform] ?? platform}</button>)}
    </div> : null}
  </li>;
}

/** The space's current waiver, shown before the guest accepts it: since 0.12.0 a live pass holder
 *  may read it. Accepting waits for the text; only a failed read falls back to the desk. */
function WaiverStep({ makerspaceId, accepting, onAccept }: { makerspaceId: number; accepting: boolean; onAccept: () => void }) {
  const waiver = useQuery({ queryKey: ["member", "guest-waiver", makerspaceId], retry: false,
    queryFn: () => memberRequest<{ has_waiver: boolean; body?: string; version?: string }>(`/member/makerspaces/${makerspaceId}/waiver`) });
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Accept the space's waiver before you arrive.`}</p>
    {waiver.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading the waiver…`}</p> : null}
    {waiver.data?.has_waiver ? <div tabIndex={0} role="region" aria-label={waiver.data.version ? t`Waiver, version ${waiver.data.version}` : t`Waiver`}
      className="max-h-64 max-w-prose overflow-y-auto whitespace-pre-wrap break-words rounded-control border border-line p-3 text-sm text-muted">{waiver.data.body}</div> : null}
    {waiver.isError ? <p className="text-sm text-muted">{t`Ask staff at the desk to show you the waiver text, or accept it there.`}</p> : null}
    <button type="button" className="desk-button-brand min-h-11" disabled={accepting || waiver.isLoading} onClick={onAccept}>{accepting ? t`Saving…` : t`Accept waiver`}</button>
  </div>;
}
