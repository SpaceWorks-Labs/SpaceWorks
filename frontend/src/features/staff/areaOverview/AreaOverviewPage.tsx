import { t } from "@lingui/core/macro";
import { ArrowLeft } from "lucide-react";

import { AreaOverview } from "./AreaOverview";
import type { AreaSection } from "./areaOverviewApi";

/** A list's grouped view as its own page inside the tab, with a way back to the flat list. */
export function AreaOverviewPage({ title, makerspaceId, section, onBack }: {
  title: string; makerspaceId: number; section: AreaSection; onBack: () => void;
}) {
  return <section className="grid min-w-0 gap-4" aria-labelledby="area-overview-heading">
    <header className="flex flex-wrap items-center gap-3">
      <button type="button" className="desk-button" onClick={onBack}><ArrowLeft aria-hidden="true" size={16} />{t`Back to the list`}</button>
      <h2 id="area-overview-heading" className="title-page">{title}</h2>
    </header>
    <AreaOverview makerspaceId={makerspaceId} section={section} />
  </section>;
}
