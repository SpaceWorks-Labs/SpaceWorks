import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { staffRequest } from "../../lib/api";
import { evidenceErrorText } from "../staff/evidenceUi";
import type { RecoveryReplay } from "./useKioskReplays";
import { replayGuidance } from "./replayRecoveryGuidance";

export function KioskReplayDetail({ row }: { row: RecoveryReplay }) {
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function preview() {
    setError(null); setUrl(null); setPending(true);
    try { setUrl((await staffRequest<{ url: string }>(`/admin/evidence/${row.evidence_id}`)).url); }
    catch (failure) { setError(evidenceErrorText(failure)); }
    finally { setPending(false); }
  }
  return <div className="grid gap-2 text-sm">
    <p className="[overflow-wrap:anywhere]">{row.failure_detail} <span className="code-text">({row.failure_code})</span></p>
    <p>{replayGuidance(row.failure_code)}</p>
    <p>{row.station_name} · {row.operator_display} · {new Date(row.completed_at).toLocaleString(formatLocale())}</p>
    <p className="break-all">{t`Aggregate ${row.aggregate_id} · sequence ${row.sequence}`}</p>
    {row.recovery_request_id ? <p>{t`Request #${row.recovery_request_id}`}</p> : null}
    {row.recovery_loan_id ? <p>{t`Direct loan #${row.recovery_loan_id}`}</p> : null}
    {row.predecessor_id ? <p className="break-all">{t`Predecessor ${row.predecessor_id} · `}{row.predecessor_state}</p> : null}
    <p className="text-muted">{t`Recovery retained until at least ${new Date(row.retained_until).toLocaleString(formatLocale())}. Evidence has its own retention policy.`}</p>
    {row.evidence_id && row.can_view_evidence ? <button type="button" className="desk-button-brand" disabled={pending} onClick={() => { void preview(); }}>{pending ? t`Loading evidence…` : t`Preview failed evidence`}</button> : null}
    {url ? <a className="desk-button-brand" href={url} target="_blank" rel="noopener noreferrer">{t`Open failed evidence photo`}</a> : null}
    {error ? <p role="alert" className="text-danger">{error}</p> : null}
    {row.resolution_code ? <p role="status">{t`Resolved: ${row.resolution_code.replace(/_/g, " ")} · `}{row.resolved_by_display}
      {row.replacement_command_id ? t` · replacement ${row.replacement_command_id}` : ""}</p> : null}
  </div>;
}
