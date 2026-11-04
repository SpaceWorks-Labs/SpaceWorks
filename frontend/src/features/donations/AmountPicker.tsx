import { Field, ProgressBar } from "../../components/ui";
import { money, type Campaign, type DonationPage } from "./donationsApi";

/** Suggested amounts as one-tap choices plus a free amount at or above the space's minimum. */
export function AmountPicker({ page, amount, onAmount }: {
  page: DonationPage; amount: string; onAmount: (value: string) => void;
}) {
  return <fieldset className="grid gap-3">
    <legend className="text-sm font-semibold text-ink">How much</legend>
    {page.suggested_amounts.length ? <div className="flex flex-wrap gap-2" role="group" aria-label="Suggested amounts">
      {page.suggested_amounts.map(value => <button key={value} type="button" aria-pressed={amount === value}
        className={amount === value ? "desk-button-primary tabular-nums" : "desk-button tabular-nums"}
        onClick={() => onAmount(value)}>{money(page.currency, value)}</button>)}
    </div> : null}
    <Field label={`Amount (${page.currency.toUpperCase()})`} hint={`The smallest gift here is ${money(page.currency, page.minimum_amount)}.`}>
      <input className="desk-input tabular-nums" inputMode="decimal" required pattern="[0-9]+(\.[0-9]{1,2})?"
        value={amount} onChange={event => onAmount(event.target.value)} />
    </Field>
  </fieldset>;
}

function CampaignProgress({ campaign }: { campaign: Campaign }) {
  if (!campaign.goal_amount) return null;
  const share = Number(campaign.raised_amount) / Number(campaign.goal_amount);
  return <div className="grid gap-1">
    <ProgressBar value={share} label={`${campaign.name}: ${Math.round(share * 100)} percent of the goal raised`} />
    <p className="text-xs text-muted tabular-nums">{money(campaign.currency, campaign.raised_amount)} of {money(campaign.currency, campaign.goal_amount)}</p>
  </div>;
}

/** "General donation" or one open campaign or fund; a goal shows how far along it is. */
export function CampaignPicker({ campaigns, value, onChange }: {
  campaigns: Campaign[]; value: number | null; onChange: (value: number | null) => void;
}) {
  if (!campaigns.length) return null;
  return <fieldset className="grid gap-2">
    <legend className="text-sm font-semibold text-ink">What it goes to</legend>
    <label className="flex min-h-11 items-center gap-2 text-sm">
      <input type="radio" name="campaign" checked={value === null} onChange={() => onChange(null)} />Wherever it helps most
    </label>
    {campaigns.map(campaign => <label key={campaign.id} className="grid gap-1 rounded-md border border-line p-3 text-sm">
      <span className="flex min-h-11 items-center gap-2">
        <input type="radio" name="campaign" checked={value === campaign.id} onChange={() => onChange(campaign.id)} />
        <span className="font-semibold text-ink">{campaign.name}</span>
        <span className="text-xs text-muted">{campaign.kind === "fund" ? "Fund" : "Campaign"}</span>
      </span>
      {campaign.description ? <span className="text-muted">{campaign.description}</span> : null}
      <CampaignProgress campaign={campaign} />
    </label>)}
  </fieldset>;
}
