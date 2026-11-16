import { t } from "@lingui/core/macro";

import { type DonationPage } from "./donationsApi";

/** Decision 242(m): who receives the gift and what receipt the giver gets, in plain words. */
export function NonprofitNote({ page }: { page: DonationPage }) {
  const profile = page.nonprofit;
  return <div className="grid gap-1 text-xs text-muted">
    {profile?.is_nonprofit ? <p>{[profile.legal_name || page.makerspace, t`a non-profit`,
      profile.registration_number ? t`registration ${profile.registration_number}` : ""].filter(Boolean).join(", ")}.</p> : null}
    {profile?.is_nonprofit && profile.exemptions.length ? <p>{profile.exemptions.map(row => `${row.label}: ${row.number}`).join(" · ")}</p> : null}
    {page.tax_receipts_available ? <p>{t`You get a receipt by email once your gift arrives; ask above for a tax receipt.`}</p>
      : <p>{page.receipt_note || t`You get a receipt by email once your gift arrives. It is not a tax receipt.`}</p>}
  </div>;
}
