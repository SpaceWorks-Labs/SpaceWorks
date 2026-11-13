import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { RelativeTime } from "../../../../../components/ui";
import { adapterErrorMessage } from "./adapterCopy";
import { ARTIFACT_DAYS, type Artifact, type ArtifactKind, type ArtifactUrl } from "./adaptersMediaApi";
import { LogoLoader } from "../../../../../components/LogoLoader";

export function artifactKindLabel(kind: ArtifactKind | string): string {
  switch (kind) {
    case "timelapse": return t`Timelapse`;
    case "thumbnail": return t`Thumbnail`;
    case "preview": return t`Job preview`;
    case "failure_snapshot": return t`Failure snapshot`;
    case "log_bundle": return t`Log bundle`;
    case "audio_recording": return t`Audio recording`;
    default: return kind;
  }
}
const sizeLabel = (bytes: number) => bytes >= 1_048_576 ? t`${(bytes / 1_048_576).toFixed(1)} MB` : t`${Math.max(1, Math.round(bytes / 1024))} KB`;

/** The private bytes of one artifact through a short-lived URL: images and video inline, audio with controls, bundles as a download. */
function ArtifactPlayer({ row, getUrl }: { row: Artifact; getUrl: (id: string) => Promise<ArtifactUrl> }) {
  const inline = row.content_type.startsWith("image/");
  const [opened, setOpened] = useState(inline);
  const url = useQuery({ queryKey: ["device-adapters", "artifact-url", row.id], queryFn: () => getUrl(row.id), enabled: opened && row.status === "ready", staleTime: 120_000 });
  if (row.status === "purged") return <p className="text-sm text-muted">{t`Deleted after its retention period.`}</p>;
  if (!opened) return <button type="button" className="desk-button justify-self-start" onClick={() => setOpened(true)}>{row.content_type.startsWith("video/") ? t`Play` : row.content_type.startsWith("audio/") ? t`Listen` : t`Open`}</button>;
  if (url.isError) return <p role="alert" className="text-sm text-danger">{adapterErrorMessage(url.error)}</p>;
  if (!url.data) return <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" />;
  const label = artifactKindLabel(row.kind);
  if (row.content_type.startsWith("image/")) return <img src={url.data.url} alt={label} className="max-h-48 rounded-lg border border-line object-contain" />;
  if (row.content_type.startsWith("video/")) return <video src={url.data.url} controls preload="metadata" aria-label={label} className="max-h-72 w-full rounded-lg border border-line" />;
  if (row.content_type.startsWith("audio/")) return <audio src={url.data.url} controls aria-label={label} />;
  return <a className="desk-button justify-self-start" href={url.data.url} rel="noopener noreferrer" download>{t`Download`}</a>;
}

export function ArtifactGallery({ rows, getUrl }: { rows: Artifact[]; getUrl: (id: string) => Promise<ArtifactUrl> }) {
  if (!rows.length) return <p className="text-sm text-muted">{t`Nothing uploaded yet.`}</p>;
  return <ul className="grid gap-3 sm:grid-cols-2" aria-label={t`Uploaded files`}>
    {rows.map(row => <li key={row.id} className="grid content-start gap-2 rounded-2xl border border-line bg-panel p-3">
      <p className="font-medium">{artifactKindLabel(row.kind)}</p>
      <p className="text-xs text-muted">{sizeLabel(row.size_bytes)} · <RelativeTime date={row.created_at} />
        {row.service_request_id ? <> · {t`Job ${row.service_request_id}`}</> : null}</p>
      <ArtifactPlayer row={row} getUrl={getUrl} />
      <p className="text-xs text-muted">{t`Private. Kept ${ARTIFACT_DAYS[row.kind] ?? 0} days, then deleted.`}</p>
    </li>)}
  </ul>;
}
