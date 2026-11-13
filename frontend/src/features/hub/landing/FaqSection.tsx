import { t } from "@lingui/core/macro";
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { DOCS_LINKS } from "../hubLinks";

function questions() {
  return [
    { q: t`Is Space Works really free?`,
      a: t`Yes. It is free software under the GNU Affero General Public License, version 3 or later. You can use it, study it and change it, with no licence fee. If you offer a changed version to other people over a network, you share your changes under the same licence.` },
    { q: t`Do I need to be a developer to run it?`,
      a: t`No. You need a Linux server (or a Mac to try it out) and a web address. The installer asks plain questions and explains each one; updating is the same command again.` },
    { q: t`Can several makerspaces share one server?`,
      a: t`Yes. Each space has its own inventory, team, public page, notifications and audit trail, and staff only ever see the spaces they belong to. Hosting other people’s spaces is a separate switch the server owner turns on.` },
    { q: t`What happens to the handover photos?`,
      a: t`They are kept in private storage and shown through short-lived links. A space can let photo files expire after a retention period; the record of the scan, the remark and who did what stays.` },
    { q: t`Can we take payments?`,
      a: t`Money owed is tracked even without a payment provider, and staff can record cash or bank transfers with a receipt. Online checkout through Stripe or Razorpay is optional.` },
    { q: t`Is there a mobile app?`,
      a: t`Space Works works in the browser on any phone today, and members can install their member area to the home screen. The native Android and iOS apps are released too: download them from GitHub Releases.` },
  ];
}

/** Native disclosure widgets: keyboard and screen-reader behaviour for free, and they print open. */
export function FaqSection() {
  return <section id="faq" aria-labelledby="faq-title" className="sw-hub-section">
    <div className="sw-hub-wrap grid gap-10 lg:grid-cols-[minmax(0,4fr)_minmax(0,7fr)] lg:gap-16">
      <div className="grid content-start gap-5">
        <h2 id="faq-title" className="sw-hub-h2">{t`Questions people ask first.`}</h2>
        <p className="sw-hub-lede">{t`Anything else is in the docs.`} <Link to={DOCS_LINKS.home} className="sw-hub-inline-link">{t`Browse the documentation`}</Link></p>
      </div>
      <div className="grid">
        {questions().map(({ q, a }) => <details key={q} className="sw-hub-faq group">
          <summary><span>{q}</span><Plus size={20} aria-hidden="true" className="shrink-0 transition-transform duration-200 group-open:rotate-45" /></summary>
          <p>{a}</p>
        </details>)}
      </div>
    </div>
  </section>;
}
