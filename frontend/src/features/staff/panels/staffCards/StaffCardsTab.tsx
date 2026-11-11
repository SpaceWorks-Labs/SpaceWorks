// "Staff cards" tab of the Member cards screen: the register, numbering, the staff design and bulk print jobs.
// Shown only while the `membership.staff_cards` switch is on; the routes answer 404 otherwise.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { SegmentedControl } from "../../../../components/ui";
import { StaffCardDesign } from "./StaffCardDesign";
import { StaffCardJobs } from "./StaffCardJobs";
import { StaffCardsList } from "./StaffCardsList";
import { StaffNumbering } from "./StaffNumbering";

type View = "cards" | "numbering" | "design" | "jobs";

export function StaffCardsTab({ makerspaceId, deskPrint }: { makerspaceId: number; deskPrint: boolean }) {
  const [view, setView] = useState<View>("cards");
  return <div className="grid gap-4">
    <SegmentedControl label={t`Staff cards section`} value={view} onChange={(value) => setView(value as View)}
      options={[{ value: "cards", label: t`Staff` }, { value: "numbering", label: t`Numbering` },
        { value: "design", label: t`Design` }, { value: "jobs", label: t`Print jobs` }]} />
    {view === "cards" ? <StaffCardsList makerspaceId={makerspaceId} deskPrint={deskPrint} /> : null}
    {view === "numbering" ? <StaffNumbering makerspaceId={makerspaceId} /> : null}
    {view === "design" ? <StaffCardDesign makerspaceId={makerspaceId} /> : null}
    {view === "jobs" ? <StaffCardJobs makerspaceId={makerspaceId} /> : null}
  </div>;
}
