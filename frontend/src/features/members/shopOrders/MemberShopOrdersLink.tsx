import { t } from "@lingui/core/macro";
import { Link } from "react-router-dom";

/** Points at `member/shop-orders`; shown in the member area when this space runs a shop. */
export function MemberShopOrdersLink({ slug }: { slug?: string }) {
  return <section className="desk-panel p-5">
    <h2 className="title-panel">{t`Shop orders`}</h2>
    <p className="mt-1 text-sm text-muted">{t`Pickup codes, receipts and anything still to pay for.`}</p>
    <Link className="desk-button mt-4 inline-flex min-h-11" to={`${slug ? `/m/${slug}/member` : "/member"}/shop-orders`}>{t`View my shop orders`}</Link>
  </section>;
}
