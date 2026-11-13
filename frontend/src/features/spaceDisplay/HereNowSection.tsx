import { t } from "@lingui/core/macro";
import { PatchMoment } from "../../components/delight/PatchMoment";
import { MakerspaceSection } from "../public/MakerspaceSection";
import { useHereNow } from "./api";
import { othersLabel, PersonCard } from "./PersonCard";

/**
 * "Here now" on the space's public page (decision 307a/b). The server decides who is named for this
 * viewer; this component only draws it. Hidden entirely when the presence module is off or the
 * request fails, because an absent section is better than a wrong count.
 */
export function HereNowSection({ slug, enabled }: { slug: string; enabled: boolean }) {
  const query = useHereNow(slug, enabled);
  if (!enabled || !query.data) return null;
  const { people, others_count: others, total } = query.data;
  return <MakerspaceSection id="here-now" title={t`Here now`}
    subtitle={total ? (people.length ? t`Makers checked in at the space.` : t`People are checked in right now.`) : undefined}>
    {total === 0
      ? <div className="flex items-center gap-4 rounded-2xl border border-dashed border-line p-5">
        <PatchMoment className="sw-features-patch" />
        <p role="status" className="text-[15px] text-muted">{t`No one is checked in right now.`}</p>
      </div>
      : <div className="grid gap-3">
        {people.length ? <ul aria-label={t`People here now`} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {people.map((card) => <li key={`${card.handle ?? card.display_name}-${card.since}`}><PersonCard card={card} /></li>)}
        </ul> : null}
        {others ? <p role="status" className="text-sm font-semibold text-ink">{othersLabel(others, people.length > 0)}</p> : null}
        {query.data.audience === "public" && others ? <p className="text-sm text-muted">{t`Sign in to see more of who is here.`}</p> : null}
      </div>}
  </MakerspaceSection>;
}
