import { t } from "@lingui/core/macro";
import { formatMoney } from "../../lib/money";
import { Card, Field, ProgressBar } from "../../components/ui";
import { type Campaign, type DonationPage } from "./donationsApi";

/** Suggested amounts as one-tap choices plus a free amount at or above the space's minimum. */
export function AmountPicker({ page, amount, onAmount }: {
  page: DonationPage; amount: string; onAmount: (value: string) => void;
}) {
  return <fieldset className="grid gap-3">
    <legend className="text-sm font-semibold text-ink">{t`How much`}</legend>
    {page.suggested_amounts.length ? <div className="flex flex-wrap gap-2" role="group" aria-label={t`Suggested amounts`}>
      {page.suggested_amounts.map(value => <button key={value} type="button" aria-pressed={amount === value}
        className={amount === value ? "desk-button-primary tabular-nums" : "desk-button tabular-nums"}
        onClick={() => onAmount(value)}>{formatMoney(value, page.currency)}</button>)}
    </div> : null}
    <Field label={t`Amount (${page.currency.toUpperCase()})`} hint={t`The smallest gift here is ${formatMoney(page.minimum_amount, page.currency)}.`}>
      <input className="desk-input tabular-nums" inputMode="decimal" required pattern="[0-9]+(\.[0-9]{1,3})?"
        value={amount} onChange={event => onAmount(event.target.value)} />
    </Field>
  </fieldset>;
}

function CampaignProgress({ campaign }: { campaign: Campaign }) {
  if (!campaign.goal_amount) return null;
  const share = Number(campaign.raised_amount) / Number(campaign.goal_amount);
  return <div className="grid gap-1">
    <ProgressBar value={Math.min(share, 1)} label={t`${campaign.name}: ${Math.round(share * 100)} percent of the goal raised`} />
    <p className="text-xs text-muted tabular-nums">{t`${formatMoney(campaign.raised_amount, campaign.currency)} of ${formatMoney(campaign.goal_amount, campaign.currency)}`}</p>
  </div>;
}

/** Decision 242(m): one campaign's own page header: its goal bar and the supporters who chose to be named. */
export function CampaignHero({ campaign }: { campaign: Campaign }) {
  const count = campaign.supporter_count ?? 0;
  const named = campaign.supporters ?? [];
  return <Card><div className="grid gap-3">
    <h2 className="title-section">{campaign.name}</h2>
    {campaign.description ? <p className="whitespace-pre-wrap text-sm">{campaign.description}</p> : null}
    <CampaignProgress campaign={campaign} />
    {!campaign.goal_amount ? <p className="text-sm text-muted tabular-nums">{t`${formatMoney(campaign.raised_amount, campaign.currency)} raised so far`}</p> : null}
    {count ? <p className="text-sm text-muted">{count === 1 ? t`1 supporter so far.` : t`${count} supporters so far.`}</p> : null}
    {named.length ? <p className="text-sm">{t`Thank you to ${named.join(", ")}, and everyone who gave anonymously.`}</p> : null}
  </div></Card>;
}

/** "General donation" or one open campaign or fund; a goal shows how far along it is. */
export function CampaignPicker({ campaigns, value, onChange, pageHref }: {
  campaigns: Campaign[]; value: number | null; onChange: (value: number | null) => void; pageHref?: (slug: string) => string;
}) {
  if (!campaigns.length) return null;
  return <fieldset className="grid gap-2">
    <legend className="text-sm font-semibold text-ink">{t`What it goes to`}</legend>
    <label className="flex min-h-11 items-center gap-2 text-sm">
      <input type="radio" name="campaign" checked={value === null} onChange={() => onChange(null)} />{t`Wherever it helps most`}</label>
    {campaigns.map(campaign => <label key={campaign.id} className="grid gap-1 rounded-md border border-line p-3 text-sm">
      <span className="flex min-h-11 items-center gap-2">
        <input type="radio" name="campaign" checked={value === campaign.id} onChange={() => onChange(campaign.id)} />
        <span className="font-semibold text-ink">{campaign.name}</span>
        <span className="text-xs text-muted">{campaign.kind === "fund" ? t`Fund` : t`Campaign`}</span>
      </span>
      {campaign.description ? <span className="text-muted">{campaign.description}</span> : null}
      <CampaignProgress campaign={campaign} />
      {pageHref ? <a className="text-xs underline" href={pageHref(campaign.slug)}>{t`Campaign page`}</a> : null}
    </label>)}
  </fieldset>;
}
