import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { Award } from "lucide-react";
import { CertificatePublicationControls } from "./CertificatePublicationControls";
import { IssuedCertificatesList } from "./IssuedCertificatesList";
import { useBatch, useIssue, useIssuePlan, useSample, type IssueGroup, type IssuePlan } from "./issueApi";

const GROUPS: { value: IssueGroup; label: string; hint: string }[] = [
  { value: "attendance", label: t`Attendance`, hint: t`Everyone marked as attended.` },
  { value: "participants", label: t`Participants`, hint: t`Members of teams with an eligible project.` },
  { value: "awards", label: t`Winners and finalists`, hint: t`From the published results: 1st place is a winner, other places finalists.` },
  { value: "roles", label: t`Thank-yous`, hint: t`Volunteers, mentors and judges with recorded work, and approved co-organisers.` },
];

/** Plan, preview and issue certificates in bulk; then follow the batch and manage what was issued. */
export function BulkCertificates({ eventId }: { eventId: number }) {
  const [groups, setGroups] = useState<IssueGroup[]>(["attendance"]);
  const [plan, setPlan] = useState<IssuePlan | null>(null);
  const [publish, setPublish] = useState(true);
  const [confirmed, setConfirmed] = useState(false);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [sampleUrl, setSampleUrl] = useState<string | null>(null);
  const planner = useIssuePlan(eventId), sample = useSample(eventId), issue = useIssue(eventId), batch = useBatch(eventId, batchId);
  useEffect(() => () => { if (sampleUrl) URL.revokeObjectURL(sampleUrl); }, [sampleUrl]);
  const error = planner.error || sample.error || issue.error || batch.error;
  const reset = () => { setPlan(null); setConfirmed(false); setSampleUrl(null); };
  return <details className="rounded-control border border-line p-3">
    <summary className="min-h-11 cursor-pointer font-semibold text-ink"><span className="inline-flex items-center gap-2"><Award size={18} aria-hidden="true" />{t`Issue certificates`}</span></summary>
    <div className="mt-3 grid gap-4">
      <fieldset className="grid gap-2"><legend className="text-sm font-semibold text-ink">{t`Who should receive one?`}</legend>
        {GROUPS.map((group) => <label key={group.value} className="flex min-h-11 items-start gap-3 text-sm">
          <input type="checkbox" className="mt-1 h-5 w-5" checked={groups.includes(group.value)} onChange={(event) => {
            reset(); setGroups(event.target.checked ? [...groups, group.value] : groups.filter((item) => item !== group.value));
          }} /><span><span className="font-semibold text-ink">{group.label}.</span> {group.hint}</span></label>)}
      </fieldset>
      <button type="button" className="desk-button justify-self-start" disabled={!groups.length || planner.isPending}
        onClick={() => { reset(); planner.mutate(groups, { onSuccess: (value) => setPlan(value) }); }}>{planner.isPending ? t`Checking who is eligible…` : t`Preview recipients`}</button>
      {plan ? <div className="grid gap-3">
        <p className="font-semibold text-ink">{t`${plan.recipients.length} will receive a certificate`}{plan.skipped.length ? t`; ${plan.skipped.length} skipped` : ""}.</p>
        {Object.keys(plan.counts).length ? <ul className="flex flex-wrap gap-2 text-sm">{Object.entries(plan.counts).map(([kind, count]) => <li key={kind}
          className="rounded-control border border-line px-3 py-1">{plan.recipients.find((row) => row.kind === kind)?.kind_title}: {count}</li>)}</ul> : null}
        {plan.recipients.length ? <div className="max-h-72 overflow-auto rounded-control border border-line"><table className="w-full text-left text-sm">
          <caption className="sr-only">{t`Recipients and their certificate kind`}</caption>
          <thead className="sticky top-0 bg-panel"><tr><th scope="col" className="p-2">{t`Recipient`}</th><th scope="col" className="p-2">{t`Certificate`}</th></tr></thead>
          <tbody>{plan.recipients.map((row) => <tr key={`${row.subject_kind}-${row.subject_id}-${row.kind}-${row.award_id}`} className="border-t border-line">
            <td className="p-2 text-ink">{row.name}</td><td className="p-2">{row.kind_title}{row.award ? ` · ${row.award}` : ""}</td></tr>)}</tbody></table></div> : null}
        {plan.skipped.length ? <details><summary className="min-h-11 cursor-pointer text-sm font-semibold text-ink">{t`Skipped (${plan.skipped.length})`}</summary>
          <ul className="mt-2 grid gap-1 text-sm">{plan.skipped.map((row) => <li key={`${row.subject_kind}-${row.subject_id}-${row.kind}-${row.award_id}`}>
            <span className="text-ink">{row.name}</span> · {row.kind_title}: <span className="text-muted">{row.reason}</span></li>)}</ul></details> : null}
        {plan.recipients.length ? <>
          <button type="button" className="desk-button justify-self-start" disabled={sample.isPending} onClick={() => sample.mutate(plan.recipients[0],
            { onSuccess: (blob) => setSampleUrl(URL.createObjectURL(blob)) })}>{sample.isPending ? t`Rendering…` : t`Show ${plan.recipients[0].name}'s certificate`}</button>
          {sampleUrl ? <iframe className="h-96 w-full rounded-control border border-line" src={sampleUrl} title={t`Sample certificate for the first recipient`} /> : null}
          <label className="flex min-h-11 items-start gap-3 text-sm"><input type="checkbox" className="mt-1 h-5 w-5" checked={publish} onChange={(event) => setPublish(event.target.checked)} />
            <span>{t`Let anyone with the link or QR code check these certificates (issuer, event, date, kind and status; names only if the holder chooses).`}</span></label>
          <label className="flex min-h-11 items-start gap-3 text-sm"><input type="checkbox" className="mt-1 h-5 w-5" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
            <span>{t`Issue ${plan.recipients.length} certificate${plan.recipients.length === 1 ? "" : "s"} as listed.`}</span></label>
          <button type="button" className="desk-button-primary justify-self-start" disabled={!confirmed || issue.isPending}
            onClick={() => issue.mutate({ plan, publish }, { onSuccess: (value) => { setBatchId(value.id); reset(); } })}>{t`Issue certificates`}</button>
        </> : null}
      </div> : null}
      {batch.data ? <p role="status" className="text-sm text-ink">{batch.data.state === "completed" ? t`Done` : t`Issuing`}: {batch.data.completed} of {batch.data.total} issued{batch.data.failures.length ? t`, ${batch.data.failures.length} need review` : ""}.
        Certificates waiting for a signatory's approval are issued as soon as they approve.</p> : null}
      {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
      <IssuedCertificatesList eventId={eventId} />
      <CertificatePublicationControls eventId={eventId} />
    </div>
  </details>;
}
