// Bulk staff-card output as server jobs: print sheets (A4 or Letter with crop marks, or one card per page),
// one PDF per person, or a ZIP. Covers every live staff card; tick cards in the register to print only those.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { ErrorBlock, Field, SegmentedControl } from "../../../../components/ui";
import { CardJobList, useStartCardJob, type CardJobKind } from "../../../cards/cardJobs";
import { staffCardJobsPath } from "./api";

type Paper = "a4" | "letter" | "per_card";

export function StaffCardJobs({ makerspaceId }: { makerspaceId: number }) {
  const path = staffCardJobsPath(makerspaceId);
  const start = useStartCardJob(path);
  const [kind, setKind] = useState<Extract<CardJobKind, "bulk_sheet" | "bulk_per_person" | "zip">>("bulk_sheet");
  const [paper, setPaper] = useState<Paper>("a4");
  const [order, setOrder] = useState<"duplex" | "fronts_then_backs">("duplex");
  const [cropMarks, setCropMarks] = useState(true);
  const sheet = kind === "bulk_sheet";

  return <div className="grid max-w-3xl gap-4">
    <section className="grid gap-3 rounded-card border border-line bg-panel p-4" aria-label={t`Make a print job`}>
      <Field label={t`Output`}>
        <select className="desk-input min-h-11" value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}>
          <option value="bulk_sheet">{t`Print sheets (PDF)`}</option>
          <option value="bulk_per_person">{t`One PDF per card`}</option>
          <option value="zip">{t`All cards (ZIP)`}</option>
        </select>
      </Field>
      {sheet ? <div className="flex flex-wrap items-end gap-3">
        <SegmentedControl label={t`Paper`} value={paper} onChange={(value) => setPaper(value as Paper)}
          options={[{ value: "a4", label: "A4" }, { value: "letter", label: t`Letter` }, { value: "per_card", label: t`One card per page` }]} />
        <SegmentedControl label={t`Page order`} value={order} onChange={(value) => setOrder(value as typeof order)}
          options={[{ value: "duplex", label: t`Backs mirrored for duplex` }, { value: "fronts_then_backs", label: t`Fronts then backs` }]} />
        <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-5 w-5" checked={cropMarks} disabled={paper === "per_card"} onChange={(event) => setCropMarks(event.target.checked)} />
          {t`Crop marks`}</label>
      </div> : null}
      <p className="text-xs text-muted">{t`Covers every live staff card. Tick people in the register first to print only those.`}</p>
      {start.error ? <ErrorBlock error={start.error} /> : null}
      <button type="button" className="desk-button-primary min-h-11 w-fit" disabled={start.isPending}
        onClick={() => start.mutate({ kind, ...(sheet ? { paper, order, crop_marks: cropMarks } : {}) })}>
        {start.isPending ? t`Starting…` : t`Start job`}</button>
    </section>
    <CardJobList listPath={path} />
  </div>;
}
