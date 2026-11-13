import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { adapterErrorMessage } from "../staff/panels/machine/adapters/adapterCopy";
import { ArtifactGallery } from "../staff/panels/machine/adapters/ArtifactGallery";
import { DetectionList } from "../staff/panels/machine/adapters/AdapterMedia";
import { mediaApi, mediaKeys } from "../staff/panels/machine/adapters/adaptersMediaApi";

/**
 * What the machine's device produced for THIS job: thumbnails, previews, timelapses and failure snapshots
 * (`machines.integrations.artifacts`) and detection alerts (`.detections`). The server answers 404 for anyone but the
 * job owner, and audio and log bundles are never shown here. Nothing renders while there is nothing to show.
 */
export function MemberJobMedia({ jobId, artifacts, detections }: { jobId: number; artifacts: boolean; detections: boolean }) {
  const files = useQuery({ queryKey: mediaKeys.jobArtifacts(jobId), queryFn: () => mediaApi.jobArtifacts(jobId), enabled: artifacts, retry: false });
  const alerts = useQuery({ queryKey: mediaKeys.jobDetections(jobId), queryFn: () => mediaApi.jobDetections(jobId), enabled: detections, retry: false, refetchInterval: 20_000 });
  const fileRows = files.data?.results ?? [];
  const alertRows = alerts.data?.results ?? [];
  if (!fileRows.length && !alertRows.length && !files.isError && !alerts.isError) return null;
  return <section className="desk-panel grid gap-3 p-5" aria-label={t`From your machine`}>
    <h2 className="title-panel">{t`From your machine`}</h2>
    <p className="text-sm text-muted">{t`Pictures and alerts your machine's device sent for this job. Only you and staff can see them, and they are deleted after a while.`}</p>
    {alertRows.length ? <><h3 className="title-section">{t`Alerts`}</h3><DetectionList rows={alertRows} /></> : null}
    {fileRows.length ? <><h3 className="title-section">{t`Pictures and timelapses`}</h3><ArtifactGallery rows={fileRows} getUrl={mediaApi.jobArtifactUrl} /></> : null}
    {files.isError || alerts.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(files.error ?? alerts.error)}</p> : null}
  </section>;
}
