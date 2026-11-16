import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FlowLayout } from "../../components/layouts";
import { ErrorText } from "../../components/ui";
import type { BackupArchive, RestoreOperation } from "./backupApi";

export function BackupRestoreDialog({ archives, pending, error, onCancel, onRestore }: {
  archives: BackupArchive[]; pending: boolean; error: Error | null; onCancel: () => void;
  onRestore: (id: string, kind: RestoreOperation["kind"]) => void;
}) {
  const [archiveId, setArchiveId] = useState(archives[0]?.id ?? "");
  const [kind, setKind] = useState<RestoreOperation["kind"]>("rollback_in_place");
  const [confirmation, setConfirmation] = useState("");
  return <FlowLayout presentation="dialog" open title={t`Restore this deployment`} subject={t`Review the archive and recovery kind. A restore replaces live deployment data.`}
    state={{ status: "ready" }} current="review" steps={[{ key: "review", label: t`Review restore`, state: "current" }]}
    work={<div className="grid gap-4">
      <label className="grid gap-2 text-sm">{t`Backup archive`}<select className="desk-input max-w-full" value={archiveId} onChange={event => setArchiveId(event.target.value)}>{archives.map(archive => <option key={archive.id} value={archive.id}>{new Date(archive.created_at).toLocaleString(formatLocale())} … {archive.id}</option>)}</select></label>
      <label className="grid gap-2 text-sm">{t`Recovery kind`}<select className="desk-input max-w-full" value={kind} onChange={event => setKind(event.target.value as RestoreOperation["kind"])}><option value="rollback_in_place">{t`Roll back in place`}</option><option value="disaster">{t`Disaster recovery`}</option></select></label>
      <label className="grid gap-2 text-sm">{t`Type deployment to confirm`}<input className="desk-input" autoComplete="off" value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
      <p className="text-sm text-danger">{t`All users may lose access while the restore runs. Review the all-table report before the final decision.`}</p>
      {error ? <ErrorText message={error.message} /> : null}
    </div>}
    footer={{ next: { label: t`Start restore…`, tone: "danger", disabled: !archiveId || confirmation !== "deployment", disabledReason: t`Choose an archive and type deployment to continue.`, pending, pendingLabel: t`Requesting restore…`, onClick: () => onRestore(archiveId, kind) } }}
    onCancel={onCancel} />;
}
