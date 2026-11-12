// Bulk cards from the member register filter (parity C11): choose who by search, standing, plan or title,
// then queue a print-sheet, per-person or ZIP job. The server resolves the same filter the register uses,
// inside the staff member's own scope, and freezes the card list when the job is queued.
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ErrorBlock, Field } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import { useStartCardJob, type CardJobKind } from "../../../cards/cardJobs";
import { lifecycleApi, lifecycleKeys } from "../../membershipLifecycleApi";
import { listPlans } from "../../membershipPlansApi";
import { memberCardJobsPath } from "./apiCards";
import { BoxArt } from "../../../../components/BoxSpinner";
import { SearchField } from "../../../../components/ui/SearchField";

const CHIPS = (): [string, string][] => [["", t`Any standing`], ["active", t`Active`], ["expiring", t`Ending soon`],
  ["grace", t`In grace`], ["lapsed", t`Lapsed`], ["upcoming", t`Starts later`]];
const KINDS = (): [Extract<CardJobKind, "bulk_sheet" | "bulk_per_person" | "zip">, string][] =>
  [["bulk_sheet", t`Print sheets (PDF)`], ["bulk_per_person", t`One PDF per card`], ["zip", t`All cards (ZIP)`]];

export function BulkFromFilter({ makerspaceId }: { makerspaceId: number }) {
  const [q, setQ] = useState("");
  const [chip, setChip] = useState("");
  const [plan, setPlan] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<CardJobKind>("bulk_sheet");
  const plans = useQuery({ queryKey: ["membership-plans", makerspaceId, "card-designs"], queryFn: () => listPlans(makerspaceId) });
  const titles = useQuery({ queryKey: lifecycleKeys.titles(makerspaceId), queryFn: () => lifecycleApi.titles(makerspaceId) });
  const start = useStartCardJob(memberCardJobsPath(makerspaceId));
  const filter = Object.fromEntries(Object.entries({ q: q.trim(), chip, plan, title, status: "active" }).filter(([, value]) => value));

  return <section className="grid gap-3 rounded-card border border-line bg-panel p-4" aria-label={t`Cards for a filtered list of members`}>
    <p className="text-sm text-muted">{t`Print cards for everyone a filter selects. It works like the member register's filter and only reaches members you may manage.`}</p>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Field label={t`Search`}><SearchField className="desk-input min-h-11" value={q} onChange={(event) => setQ(event.target.value)} /></Field>
      <Field label={t`Standing`}><select className="desk-input min-h-11" value={chip} onChange={(event) => setChip(event.target.value)}>
        {CHIPS().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field label={t`Plan`}><select className="desk-input min-h-11" value={plan} onChange={(event) => setPlan(event.target.value)}>
        <option value="">{t`Any plan`}</option>{(plans.data ?? []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
      <Field label={t`Title`}><select className="desk-input min-h-11" value={title} onChange={(event) => setTitle(event.target.value)}>
        <option value="">{t`Any title`}</option>{(titles.data ?? []).filter((row) => !row.archived_at).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></Field>
    </div>
    <div className="flex flex-wrap items-end gap-3">
      <Field label={t`Output`}><select className="desk-input min-h-11" value={kind} onChange={(event) => setKind(event.target.value as CardJobKind)}>
        {KINDS().map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <button type="button" className="desk-button-primary min-h-11" disabled={start.isPending}
        onClick={() => start.mutate({ kind, filter }, { onSuccess: () => toast(t`Job queued. Its progress shows above the table.`, { tone: "success" }) })}>
        {start.isPending ? <><BoxArt size={16} mono />{t`Starting…`}</> : t`Make cards for this filter`}</button>
    </div>
    {start.error ? <ErrorBlock error={start.error} /> : null}
  </section>;
}
