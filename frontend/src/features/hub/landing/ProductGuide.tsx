import { t } from "@lingui/core/macro";
import { Link } from "react-router-dom";
import { ProductConnections } from "./ProductConnections";

/** Catalogue details formerly in the README, reused on the landing and features overview. */
export function ProductGuide() {
  return <div className="min-w-0" data-product-guide>
    <ProductConnections />
    <section className="mt-16" aria-labelledby="product-money-title">
      <h3 id="product-money-title" className="title-section">{t`Free and paid`}</h3>
      <div className="mt-4 grid gap-4 text-muted">
        <p>{t`Every module can run free. charges.enabled is the master switch; each area's charges switch chooses whether it may charge. Prices stay saved when a switch is off and no new charge is raised. Shop catalogue and stock work free; selling requires charges.shop. Campaigns and sponsor recognition work free; accepting gifts requires charges.donations.`}</p>
        <p>{t`Membership charges can cover dues, admission, terms, renewals and guest passes. Donations can cover gifts, recurring pledges and sponsorship. The other area's fee types and charge switches are listed above.`}</p>
        <p>{t`The payments module adds Stripe or Razorpay only when its master and area switches and credentials are configured. A debt raised without a provider is unclaimed. Staff can settle it offline with an append-only receipt recording the method, reference and received date. Turning off charging never erases a debt, receipt or refund case. Due dates and billing reminders also work for offline payers.`}</p>
        <p>{t`Accounts, evidence, cards, reports, notifications, public pages, presence, security, backups and integrations carry no separate member fee. Hosting and external providers may have operating costs.`}</p>
      </div>
    </section>
    <section className="mt-16" aria-labelledby="product-limits-title">
      <h3 id="product-limits-title" className="title-section">{t`Limits`}</h3>
      <div className="mt-4 grid gap-4 text-muted">
        <p>{t`Fresh managed and self-hosted spaces have no resource quotas until the superadmin sets them. Platform defaults, hosted-plan allowances and per-space overrides live in platform limits and the control plane. Space Managers can see only their own usage. An explicit zero stops new usage; null or -1 removes a quota. Fixed validation and security bounds still apply.`}</p>
        <p>{t`Common bounds: 24 results on a default page; inventory imports up to 5,000 rows or 5 MiB; shop baskets up to 50 lines and 999 units per variant; evidence retention from 30 to 3,650 days, with 365 days as the default.`}</p>
        <p>{t`Existing records remain available. Resource and payment quotas preserve existing workflows, debt settlement and privacy requests. Required issue and return evidence must still fit upload and storage allowances; the operator must raise exhausted allowances before handover can finish.`}</p>
      </div>
      <Link to="/docs/features" className="sw-hub-inline-link mt-5 inline-block">{t`Upload checks, throttles and every limit`}</Link>
    </section>
    <section className="mt-16" aria-labelledby="product-tv-title">
      <h3 id="product-tv-title" className="title-section">{t`Public TV`}</h3>
      <p className="mt-4 text-muted">{t`Put a live screen on the workshop wall: who is here, machines in use or free, the events calendar and announcements, without contact details.`}</p>
      <ol className="mt-5 list-decimal space-y-4 pl-6 text-muted">
        <li>{t`Enable Presence and its Space display screens capability, which is off by default. Open Settings, Display screens in the staff console.`}</li>
        <li>{t`Open /display on the TV and enter its six-character pairing code in the console within 30 minutes. Or create a screen with an address and open it on the TV or in Anthias. The address is shown once; New address replaces it.`}</li>
        <li>{t`Choose Here now, events, machines, announcements, public stats, opening hours, inventory highlights or sponsors. Pick rotating, single or grid layout, theme, name privacy and refresh interval. Preview it before saving.`}</li>
      </ol>
      <div className="mt-5 flex flex-wrap gap-5">
        <Link to="/docs/how-to/display-screens" className="sw-hub-inline-link">{t`Set up display screens`}</Link>
        <Link to="/docs/how-to/anthias" className="sw-hub-inline-link">{t`Use an Anthias player`}</Link>
      </div>
    </section>
  </div>;
}
