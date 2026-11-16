import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { CheckCircle2, Eye, PenLine } from "lucide-react";
import { memberRequestBlob } from "../../../lib/api";
import { approvalPreviewPath, usePendingApprovals, type PendingApproval } from "../../staff/eventCredentials/signatoryApi";
import { CERTIFICATE_KINDS } from "../../staff/eventCredentials/designer/samples";

/** Designs that print this member's signature: review the PDF, then approve. Hidden when there are none. */
export function CertificateApprovals({ makerspaceId }: { makerspaceId: number }) {
  const { query, approve } = usePendingApprovals(makerspaceId);
  const [preview, setPreview] = useState<{ row: PendingApproval; url: string } | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  if (!query.data?.length) return null;
  const kindLabel = (kind: string) => kind ? CERTIFICATE_KINDS.find((row) => row.value === kind)?.label ?? kind : t`Default`;
  async function open(row: PendingApproval) {
    setLoading(true);
    try { setPreview({ row, url: URL.createObjectURL(await memberRequestBlob(approvalPreviewPath(makerspaceId, row))) }); }
    finally { setLoading(false); }
  }
  return <section className="grid gap-3 rounded-control border border-line p-4" aria-labelledby="certificate-approvals">
    <h3 id="certificate-approvals" className="title-section inline-flex items-center gap-2"><PenLine size={18} aria-hidden="true" />{t`Certificate designs to approve`}</h3>
    <p className="text-sm text-muted">{t`These certificate designs print your signature as ${query.data[0].name}. Certificates are issued only after you approve.`}</p>
    <ul className="grid gap-2">{query.data.map((row) => <li key={`${row.signatory_id}-${row.template_revision_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-line p-3">
      <div className="min-w-0"><p className="font-semibold text-ink">{row.event_title}</p>
        <p className="text-sm text-muted">{t`${kindLabel(row.certificate_kind)} design · signing as ${row.name}${row.title ? `, ${row.title}` : ""}`}</p></div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" disabled={loading} onClick={() => { void open(row); }}><Eye size={16} aria-hidden="true" />{t`Review design`}</button>
        {row.approved ? <span className="inline-flex min-h-11 items-center gap-1 text-sm text-success-ink"><CheckCircle2 size={16} aria-hidden="true" />{t`Approved`}</span>
          : <button type="button" className="desk-button-primary" disabled={approve.isPending} onClick={() => approve.mutate(row)}>{t`Approve`}</button>}
      </div></li>)}</ul>
    {preview ? <div className="grid gap-2"><iframe className="h-[28rem] w-full rounded-control border border-line" src={preview.url} title={t`Certificate design for ${preview.row.event_title}`} />
      <button type="button" className="desk-button justify-self-start" onClick={() => setPreview(null)}>{t`Close the design`}</button></div> : null}
    {approve.error ? <p role="alert" className="text-sm text-danger">{approve.error.message}</p> : null}
  </section>;
}
