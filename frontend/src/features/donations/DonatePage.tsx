import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { Card, Field, SegmentedControl } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { AmountPicker, CampaignPicker } from "./AmountPicker";
import { DonationShell, useDonationSpace } from "./DonationShell";
import {
  INTERVAL_LABELS, donationKeys, donationsApi, giveError, signedIn, type GiftStatus, type GiverFields, type Interval,
  type PledgeStatus,
} from "./donationsApi";
import { GiftStatusView } from "./GiftStatusView";
import { GuestIdentity, TaxReceiptFields } from "./GiverFieldsets";

type Frequency = "once" | Interval;

/**
 * The space's donation page (#128 C-14): anyone may give. Signed in, the gift is yours; otherwise
 * your name, email and the emailed code. Online payment opens the hosted checkout; without it the
 * gift waits for an offline payment the space records.
 */
export function DonatePage() {
  const { slug, path } = useDonationSpace();
  const navigate = useNavigate();
  const page = useQuery({ queryKey: donationKeys.page(slug), queryFn: () => donationsApi.page(slug), enabled: Boolean(slug),
    retry: false });
  const [amount, setAmount] = useState("");
  const [campaign, setCampaign] = useState<number | null>(null);
  const [frequency, setFrequency] = useState<Frequency>("once");
  const [note, setNote] = useState("");
  const [giver, setGiver] = useState<GiverFields>({});
  const [done, setDone] = useState<GiftStatus | null>(null);
  const member = signedIn();
  const identity = member ? {} : { donor_name: giver.donor_name, donor_email: giver.donor_email, email_code: giver.email_code };
  const tax = giver.wants_tax_receipt
    ? { wants_tax_receipt: true, donor_pan: giver.donor_pan, donor_address: giver.donor_address } : {};
  const give = useMutation({
    mutationFn: async (): Promise<GiftStatus | PledgeStatus> => frequency === "once"
      ? donationsApi.give(slug, { amount, campaign, note, ...identity, ...tax })
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
  const off = page.error instanceof StructuredApiError && page.error.status === 404;
  if (off) {
    return <DonationShell title="Support this space" state={{ status: "ready" }}>
      <Card><p className="text-sm">This space isn't taking donations online right now.</p></Card>
    </DonationShell>;
  }
  const data = page.data;
  const state = page.isLoading ? { status: "loading" as const } : page.error ? { status: "error" as const,
    error: "Couldn't load the donation page.", onRetry: () => { void page.refetch(); } } : { status: "ready" as const };
  return <DonationShell title={data ? `Support ${data.makerspace}` : "Support this space"} subtitle={data?.intro || undefined}
    state={state}>
    {done ? <GiftStatusView gift={done} /> : data ? <Card><form className="grid gap-6" aria-label="Give to this space"
      onSubmit={event => { event.preventDefault(); give.mutate(); }}>
      {data.recurring_available ? <div className="grid gap-2">
        <span className="text-sm font-semibold text-ink" aria-hidden="true">How often</span>
        <SegmentedControl label="How often" value={frequency} onChange={value => setFrequency(value as Frequency)}
          options={[{ value: "once", label: "Once" }, ...(Object.keys(INTERVAL_LABELS) as Interval[]).map(value => ({
            value, label: INTERVAL_LABELS[value] }))]} />
        {frequency !== "once" ? <p className="text-sm text-muted">Each period you get a reminder to pay. No card is stored and you can
          pause or cancel any time.</p> : null}
      </div> : null}
      <AmountPicker page={data} amount={amount} onAmount={setAmount} />
      <CampaignPicker campaigns={data.campaigns} value={campaign} onChange={setCampaign} />
      {frequency === "once" ? <Field label="A note for the space (optional)"><textarea className="desk-input" rows={2}
        maxLength={500} value={note} onChange={event => setNote(event.target.value)} /></Field> : null}
      {member ? <p className="text-sm text-muted">You're signed in, so this gift is recorded on your account.</p>
        : <GuestIdentity slug={slug} value={giver} onChange={patch => setGiver(current => ({ ...current, ...patch }))} />}
      {data.tax_receipts_available ? <TaxReceiptFields registration={data.tax_registration_number} value={giver}
        onChange={patch => setGiver(current => ({ ...current, ...patch }))} /> : null}
      {give.error ? <p role="alert" className="text-sm text-danger">{giveError(give.error)}</p> : null}
      <div className="grid gap-2">
        <button type="submit" className="desk-button-primary justify-self-start" disabled={give.isPending || !amount}>
          {give.isPending ? "Working…" : frequency === "once" ? (data.online_available ? "Continue to payment" : "Give")
            : "Make my pledge"}</button>
        {!data.online_available ? <p className="text-xs text-muted">Online payment is off here: you'll see how to pay the space
          directly.</p> : null}
      </div>
    </form></Card> : null}
  </DonationShell>;
}
