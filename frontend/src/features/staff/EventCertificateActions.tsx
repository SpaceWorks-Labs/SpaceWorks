import { t } from "@lingui/core/macro";
import { opsStatusLabel } from "./opsPresentation";
import { StatusBadge } from "../../components/ui";
import {
  useCertificateAction,
  useCertificateDownload,
  type CertificateSummary,
} from "./eventFeedbackApi";
import { eventErrorText } from "./eventUi";

export function EventCertificateActions({ certificate, eventId, makerspaceId }: {
  certificate: CertificateSummary;
  eventId: number;
  makerspaceId: number;
}) {
  const download = useCertificateDownload(eventId, makerspaceId);
  const revoke = useCertificateAction(eventId, makerspaceId, "revoke");
  const reissue = useCertificateAction(eventId, makerspaceId, "reissue");
  const error = download.error || revoke.error || reissue.error;
  const downloadLabel = certificate.status === "active" ? t`Download` : t`Prepare certificate`;
  return <div className="mt-3">
    <div className="flex flex-wrap items-center gap-2">
      <StatusBadge status={certificate.status} label={opsStatusLabel(certificate.status)} />
      <span className="tabular-nums text-xs">{t`Certificate r${certificate.revision}`}</span>
      {certificate.status === "active" || certificate.status === "pending" || certificate.status === "failed" ? <button className="desk-button" type="button" disabled={download.isPending} onClick={() => download.mutate(certificate.id, { onSuccess: (result) => window.location.assign(result.url) })}>{downloadLabel}</button> : null}
      {certificate.status === "active" ? <button className="desk-button-danger" type="button" disabled={revoke.isPending} onClick={() => revoke.mutate(certificate.id)}>{t`Revoke`}</button> : null}
      {certificate.status === "revoked" ? <button className="desk-button-success" type="button" disabled={reissue.isPending} onClick={() => reissue.mutate(certificate.id)}>{t`Reissue`}</button> : null}
    </div>
    {error ? <p className="mt-2 text-sm text-danger" role="alert">{eventErrorText(error)}</p> : null}
  </div>;
}
