import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { Card, Field, SegmentedControl } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { chargesOn } from "../../lib/charges";
import { AmountPicker, CampaignHero, CampaignPicker } from "./AmountPicker";
import { DonationShell, useDonationSpace } from "./DonationShell";
import {
  INTERVAL_LABELS, donationKeys, donationsApi, giveError, signedIn, type GiftStatus, type GiverFields, type Interval,
  type PledgeStatus,
} from "./donationsApi";
import { GiftStatusView } from "./GiftStatusView";
import { GuestIdentity, TaxReceiptFields } from "./GiverFieldsets";
import { NonprofitNote } from "./NonprofitNote";
import { BoxArt } from "../../components/BoxSpinner";

type Frequency = "once" | Interval;

/**
 * The space's donation page (#128 C-14): anyone may give. Signed in, the gift is yours; otherwise
 * your name, email and the emailed code. Online payment opens the hosted checkout; without it the
 * gift waits for an offline payment the space records.
 */
export function DonatePage() {
  const { slug, path, bootstrap } = useDonationSpace();
  // Decision 242(m): `/donate/campaign/<slug>` is one campaign's own page, its goal bar on top.
  const { campaign: campaignSlug } = useParams();
  // #184: with donation charges off the server refuses every gift, so the form never shows.
  const giving = chargesOn(bootstrap, "donations");
  const navigate = useNavigate();
  const page = useQuery({ queryKey: donationKeys.page(slug), queryFn: () => donationsApi.page(slug), enabled: Boolean(slug) && giving,
    retry: false });
  const [amount, setAmount] = useState("");
  const [campaign, setCampaign] = useState<number | null>(null);
  const [frequency, setFrequency] = useState<Frequency>("once");
  const [note, setNote] = useState("");
  const [giver, setGiver] = useState<GiverFields>({});
  const [recognize, setRecognize] = useState(false);
  const [done, setDone] = useState<GiftStatus | null>(null);
  const featured = page.data?.campaigns.find(row => row.slug === campaignSlug);
  useEffect(() => { if (featured) setCampaign(featured.id); }, [featured]);
  const member = signedIn();
  const identity = member ? {} : { donor_name: giver.donor_name, donor_email: giver.donor_email, email_code: giver.email_code };
  const tax = giver.wants_tax_receipt
    ? { wants_tax_receipt: true, donor_pan: giver.donor_pan, donor_address: giver.donor_address } : {};
  const give = useMutation({
    mutationFn: async (): Promise<GiftStatus | PledgeStatus> => frequency === "once"
      ? donationsApi.give(slug, { amount, campaign, note, ...identity, ...tax, ...(recognize && campaign ? { recognize_publicly: true } : {}) })
      : donationsApi.pledge(slug, { amount, interval: frequency, campaign, ...identity, ...tax }),
    onSuccess: result => {
      if ("interval" in result) {
        if (result.manage_token) navigate(path(`donate/pledge/${encodeURIComponent(result.manage_token)}`));
        else navigate(path("member"));
        return;
      }
      if (result.checkout_url) { window.location.assign(result.checkout_url); return; }
      if (result.status_token) { navigate(path(`donate/gift/${encodeURIComponent(result.status_token)}`)); return; }
      setDone(result);
    },
  });
  const off = !giving || (page.error instanceof StructuredApiError && page.error.status === 404);
  if (off) {
    return <DonationShell title={t`Support this space`} state={{ status: "ready" }}>
      <Card><p className="text-sm">{giving ? t`This space isn't taking donations online right now.` : t`This space isn't taking donations right now.`}</p></Card>
    </DonationShell>;
  }
  const data = page.data;
  const state = page.isLoading ? { status: "loading" as const } : page.error ? { status: "error" as const,
    error: t`Couldn't load the donation page.`, onRetry: () => { void page.refetch(); } } : { status: "ready" as const };
  return <DonationShell title={data ? t`Support ${data.makerspace}` : t`Support this space`} subtitle={data?.intro || undefined}
    state={state}>
    {!done && featured ? <CampaignHero campaign={featured} /> : null}
    {!done && data && campaignSlug && !featured ? <p className="text-sm text-muted">{t`That campaign isn't taking gifts right now. You can still give to the space.`}</p> : null}
    {done ? <GiftStatusView gift={done} /> : data ? <Card><form className="grid gap-6" aria-label={t`Give to this space`}
      onSubmit={event => { event.preventDefault(); give.mutate(); }}>
      {data.recurring_available ? <div className="grid gap-2">
        <span className="text-sm font-semibold text-ink" aria-hidden="true">{t`How often`}</span>
        <SegmentedControl label={t`How often`} value={frequency} onChange={value => setFrequency(value as Frequency)}
          options={[{ value: "once", label: t`Once` }, ...(Object.keys(INTERVAL_LABELS) as Interval[]).map(value => ({
            value, label: INTERVAL_LABELS[value] }))]} />
        {frequency !== "once" ? <p className="text-sm text-muted">{t`Each period you get a reminder to pay. No card is stored and you can pause or cancel any time.`}</p> : null}
      </div> : null}
      <AmountPicker page={data} amount={amount} onAmount={setAmount} />
      <CampaignPicker campaigns={data.campaigns} value={campaign} onChange={setCampaign}
        pageHref={value => path(`donate/campaign/${encodeURIComponent(value)}`)} />
      {campaign && frequency === "once" ? <label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={recognize} onChange={event => setRecognize(event.target.checked)} />
        {t`Name me among this campaign's supporters (otherwise my gift stays anonymous)`}</label> : null}
      {frequency === "once" ? <Field label={t`A note for the space (optional)`}><textarea className="desk-input" rows={2}
        maxLength={500} value={note} onChange={event => setNote(event.target.value)} /></Field> : null}
      {member ? <p className="text-sm text-muted">{t`You're signed in, so this gift is recorded on your account.`}</p>
        : <GuestIdentity slug={slug} value={giver} onChange={patch => setGiver(current => ({ ...current, ...patch }))} />}
      {data.tax_receipts_available ? <TaxReceiptFields registration={data.tax_registration_number} schemes={data.tax_schemes}
        needsPan={data.tax_receipt_needs_pan ?? true} value={giver}
        onChange={patch => setGiver(current => ({ ...current, ...patch }))} /> : null}
      <NonprofitNote page={data} />
      {give.error ? <p role="alert" className="text-sm text-danger">{giveError(give.error)}</p> : null}
      <div className="grid gap-2">
        <button type="submit" className="desk-button-primary justify-self-start" disabled={give.isPending || !amount}>
          {give.isPending ? <><BoxArt size={16} mono />{t`Working…`}</> : frequency === "once" ? (data.online_available ? t`Continue to payment` : t`Give`)
            : t`Make my pledge`}</button>
        {!data.online_available ? <p className="text-xs text-muted">{t`Online payment is off here: you'll see how to pay the space directly.`}</p> : null}
      </div>
    </form></Card> : null}
  </DonationShell>;
}
