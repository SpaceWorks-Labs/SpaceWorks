import { useState } from "react";
import { EmptyState, ErrorText } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { evidenceErrorText } from "../evidenceUi";
import type { HardwareRequest } from "./Queues";

export function RequestEvidence({ row }: { row: HardwareRequest }) {
  const [urls, setUrls] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const photos = [...(row.issue_evidence_id ? [{ id: row.issue_evidence_id, label: "Issue photo" }] : []),
    ...(row.return_evidence_ids ?? []).map((id, index) => ({ id, label: `Return photo${(row.return_evidence_ids?.length ?? 0) > 1 ? ` ${index + 1}` : ""}` }))];
  async function load(id: number) {
    setError(""); setBusy(id);
    try { const result = await staffRequest<{ url: string }>(`/admin/evidence/${id}`); setUrls(current => ({ ...current, [id]: result.url })); }
    catch (cause) { setError(evidenceErrorText(cause)); }
    finally { setBusy(null); }
  }
  if (!photos.length) return <EmptyState message="No photos yet. The issue photo is taken during handover." />;
  return <div className="grid gap-4"><ErrorText message={error} />{photos.map(photo => <section key={photo.id} className="grid gap-3 rounded-xl border border-line p-4">
    <h2 className="title-section">{photo.label}</h2>
    {urls[photo.id] ? <><img src={urls[photo.id]} alt={photo.label} className="max-h-72 w-full rounded-xl object-contain" />
      <a className="desk-button" href={urls[photo.id]} target="_blank" rel="noopener noreferrer">Open {photo.label.toLowerCase()} ↗</a></> : null}
    <button type="button" className="desk-button" disabled={busy !== null} onClick={() => void load(photo.id)}>{busy === photo.id ? "Loading photo…" : `View ${photo.label.toLowerCase()}`}</button>
  </section>)}</div>;
}
