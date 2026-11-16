import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { staffRequestBlob } from "../../../lib/api";

/** File links come only from the authorized immutable-answer projection. */
export function StageAnswerFiles({ eventId, value }: { eventId: number; value: unknown }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const files = Array.isArray(value) ? value.filter((file): file is { download_path: string } => {
    if (!file || typeof file !== "object" || !("download_path" in file) || typeof file.download_path !== "string") return false;
    return new RegExp(`^/admin/events/${eventId}/stage-files/[1-9][0-9]*/download/\\?`).test(file.download_path.replace(/^\/api\/v1/, ""));
  }) : [];
  if (!files.length) return <p className="text-sm text-muted">{t`No file is available for your answer disclosure.`}</p>;
  return <div className="grid gap-2">{files.map((file, index) => <button key={file.download_path} type="button" className="desk-button justify-self-start" disabled={busy} onClick={async () => {
    const active = new AbortController(); controller.current = active; setBusy(true); setError(false);
    try {
      const blob = await staffRequestBlob(file.download_path.replace(/^\/api\/v1/, ""), { cache: "no-store", signal: active.signal });
      if (active.signal.aborted) return;
      const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
      anchor.href = url; anchor.download = "stage-attachment"; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { if (!active.signal.aborted) setError(true); }
    finally { if (!active.signal.aborted) setBusy(false); }
  }}>{t`Download disclosed file ${index + 1}`}</button>)}
    {error ? <p role="alert">{t`This file could not be read. Your access or its retention period may have changed.`}</p> : null}</div>;
}
