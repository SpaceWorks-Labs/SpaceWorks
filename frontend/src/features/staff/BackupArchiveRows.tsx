import { EmptyState, ErrorText, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import type { BackupArchive } from "./backupApi";

export function ArchiveDisclosure({ deployment }: { deployment: boolean }) {
  return <p className="rounded-xl border border-line bg-surface p-4 text-sm text-ink">This {deployment ? "deployment archive contains production data and continuity secrets" : "makerspace archive contains production tenant data"}, encrypted to the configured age recipient. Downloaded copies are outside makerspace purge guarantees; delete retained copies separately.</p>;
}
export function BackupArchiveRows({ rows, onDownload, downloading }: { rows: BackupArchive[]; onDownload: (id: string) => void; downloading?: string }) {
  return <div className="grid gap-3">{!rows.length ? <EmptyState message="No backups yet. Create one before you change anything big." /> : rows.map(row => <ListRow key={row.id}
    title={row.scope === "deployment" ? "Full deployment" : "Makerspace"} identity={{ kind: "date", date: row.created_at }}
    meta={<><RelativeTime date={row.created_at} /> · {row.size_bytes ? `${(row.size_bytes / 1024 / 1024).toFixed(1)} MB` : "—"} … <StatusPill label={row.status.replace(/_/g, " ")} tone={row.status === "available" ? "success" : row.status === "failed" ? "danger" : "neutral"} />
      {row.failure_detail ? <span className="mt-2 block"><ErrorText message={row.failure_detail} /></span> : null}</>}
    right={row.status === "available" ? <button className="desk-button" type="button" disabled={downloading === row.id} onClick={() => onDownload(row.id)}>{downloading === row.id ? "Preparing link…" : "Download"}</button> : undefined} />)}</div>;
}
