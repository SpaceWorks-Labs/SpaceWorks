import { t } from "@lingui/core/macro";
import { Link } from "react-router-dom";

/** Points at `member/events/history`, which works with or without a membership here. */
export function MemberEventHistoryLink({ slug }: { slug: string }) {
  return <section className="desk-panel p-5">
    <h2 className="title-panel">{t`Your event history`}</h2>
    <p className="mt-1 text-sm text-muted">{t`Events you registered for or spoke at here, including past ones.`}</p>
    <Link className="desk-button-brand mt-4 inline-flex" to={`${slug ? `/m/${slug}/member` : "/member"}/events/history`}>{t`View event history`}</Link>
  </section>;
}
