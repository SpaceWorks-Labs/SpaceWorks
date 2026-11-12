import { LogoLoader } from "../../../components/LogoLoader";
import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { Award, BadgeCheck, Download, FileText, Image as ImageIcon, Share2 } from "lucide-react";
import { EmptyState, StatusPill } from "../../../components/ui";
import { linkedInUrl, useCertificateImage, useCertificatePdf, useHolderName, useMyCertificates, type HolderCertificate } from "./certificateApi";

const STATUS: Record<HolderCertificate["status"], { label: string; tone: "success" | "info" | "danger" | "neutral" }> = {
  active: { label: t`Ready`, tone: "success" }, pending: { label: t`Being prepared`, tone: "info" },
  rendering: { label: t`Being prepared`, tone: "info" }, failed: { label: t`Needs a retry`, tone: "neutral" }, revoked: { label: t`Withdrawn`, tone: "danger" },
};

function CertificateCard({ row, makerspaceId }: { row: HolderCertificate; makerspaceId: number }) {
  const pdf = useCertificatePdf(makerspaceId);
  const image = useCertificateImage(makerspaceId);
  const name = useHolderName(makerspaceId);
  const ready = row.status === "active";
  const error = pdf.error || image.error || name.error;
  return <li className="grid gap-3 rounded-control border border-line bg-surface p-4">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <p className="inline-flex items-center gap-2 font-semibold text-ink"><Award size={18} aria-hidden="true" />{row.kind_title}</p>
        {row.award ? <p className="text-sm font-semibold text-ink">{row.award}</p> : null}
        <p className="text-sm text-muted">{row.event_title} · {new Date(row.event_date).toLocaleDateString(formatLocale())} · {row.issuer_name}</p>
      </div>
      <StatusPill label={STATUS[row.status].label} tone={STATUS[row.status].tone} />
    </div>
    {row.status !== "revoked" ? <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button" disabled={pdf.isPending} onClick={() => pdf.mutate(row.id)}>
        <FileText size={16} aria-hidden="true" />{ready ? t`Download PDF` : row.status === "failed" ? t`Retry preparing` : t`Prepare PDF`}</button>
      {ready ? <button type="button" className="desk-button" disabled={image.isPending} onClick={() => image.mutate({ row, kind: "png" })}>
        <ImageIcon size={16} aria-hidden="true" />{t`Download image (PNG)`}</button> : null}
      {ready ? <button type="button" className="desk-button" disabled={image.isPending} onClick={() => image.mutate({ row, kind: "share-image" })}>
        <Download size={16} aria-hidden="true" />{t`Share image`}</button> : null}
      {ready && row.verifiable ? <a className="desk-button" href={linkedInUrl(row)} target="_blank" rel="noopener noreferrer">
        <Share2 size={16} aria-hidden="true" />{t`Add to LinkedIn profile`}<span className="sr-only"> {t` (opens LinkedIn in a new tab)`}</span></a> : null}
      {row.verifiable && row.verify_url ? <a className="desk-button-ghost" href={row.verify_url} target="_blank" rel="noopener noreferrer">
        <BadgeCheck size={16} aria-hidden="true" />{t`Verification page`}</a> : null}
    </div> : <p className="text-sm text-danger">{t`The organisers withdrew this certificate. Contact them if this looks wrong.`}</p>}
    {row.verifiable ? <label className="flex min-h-11 items-start gap-3 text-sm">
      <input type="checkbox" className="mt-1 h-5 w-5" checked={row.holder_name_public} disabled={name.isPending}
        onChange={(event) => name.mutate({ id: row.id, show: event.target.checked })} />
      <span>{t`Show my name on the public verification page and share image. Off by default; anyone with the link or QR code can see it while on.`}</span></label>
      : ready ? <p className="text-xs text-muted">{t`Public verification is off for this certificate, so it cannot be shared or added to LinkedIn.`}</p> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
  </li>;
}

/** Every certificate the member holds from this space, with downloads, sharing and name visibility. */
export function MyCertificates({ makerspaceId }: { makerspaceId: number }) {
  const query = useMyCertificates(makerspaceId);
  if (query.isLoading) return <LogoLoader label={t`Loading your certificates…`} />;
  if (query.isError) return <p role="alert" className="text-sm text-danger">{t`Your certificates could not be loaded. `}<button type="button" className="desk-button-ghost" onClick={() => { void query.refetch(); }}>{t`Try again`}</button></p>;
  if (!query.data?.length) return <EmptyState message={t`No certificates yet. They appear here once organisers issue them.`} />;
  return <ul className="grid gap-3" aria-label={t`My certificates`}>{query.data.map((row) => <CertificateCard key={row.id} row={row} makerspaceId={makerspaceId} />)}</ul>;
}
