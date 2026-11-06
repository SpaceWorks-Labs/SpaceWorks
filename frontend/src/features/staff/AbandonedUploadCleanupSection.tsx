import { t } from "@lingui/core/macro";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState, type FormEvent } from "react";

import type {
  EvidenceRetentionPatch,
  EvidenceRetentionPolicy,
  EvidenceRetentionPreview,
} from "./evidenceRetentionApi";

type Props = {
  policy: EvidenceRetentionPolicy;
  preview: EvidenceRetentionPreview | undefined;
  pending: boolean;
  onChange: (changes: EvidenceRetentionPatch) => void;
};

// Abandoned-upload cleanup is a separate, default-off control from object expiry: it
// deletes only old presign rows that no workflow ever consumed.
export function AbandonedUploadCleanupSection({ policy, preview, pending, onChange }: Props) {
  const [days, setDays] = useState("");
  const [daysTouched, setDaysTouched] = useState(false);
  useEffect(() => {
    setDays(String(policy.abandoned_upload_effective_days));
    setDaysTouched(false);
  }, [policy.abandoned_upload_effective_days, policy.abandoned_upload_override_days]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onChange({ abandoned_upload_retention_days: Number(days) });
  };

  return (
    <SettingsRow label={t`Abandoned upload cleanup`} helper="Removes only old upload slots that were never used by any handover. Attached evidence rows are immutable and are never deleted, and photos recorded before this feature (legacy) are never eligible."><div className="@container grid min-w-0 gap-4">


      <label className="min-h-11 mt-3 flex items-center gap-2 text-sm font-semibold text-ink">
        <input
          type="checkbox"
          checked={policy.abandoned_upload_cleanup_enabled}
          disabled={pending}
          onChange={(event) => onChange({ abandoned_upload_cleanup_enabled: event.target.checked })}
        />
        {t`Clean up never-used uploads for this space`}</label>
      <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={submit}>
        <label className="grid gap-1 text-sm font-semibold text-ink">
          {t`Abandoned upload age (days)`}<input
            className="desk-input w-40"
            type="number"
            min="1"
            max="3650"
            value={days}
            onChange={(event) => { setDays(event.target.value); setDaysTouched(true); }}
            required
          />
        </label>
        <SettingsEditorActions dirty={days !== String(policy.abandoned_upload_effective_days) || (daysTouched && policy.abandoned_upload_override_days === null)} onDiscard={() => { setDays(String(policy.abandoned_upload_effective_days)); setDaysTouched(false); }} pending={pending} disabled={pending} />
        <button
          className="desk-button"
          type="button"
          disabled={pending || policy.abandoned_upload_override_days === null}
          onClick={() => onChange({ abandoned_upload_retention_days: null })}
        >
          {t`Use platform age`}</button>
      </form>
      <p className="mt-2 text-xs text-muted">
        {t`Platform age ${policy.abandoned_upload_platform_default_days} days. `}
        {policy.abandoned_upload_global_enabled
          ? t`Cleanup is enabled for this deployment.`
          : t`Cleanup is switched off for this deployment; nothing is deleted until the operator enables it.`}
      </p>
      {preview ? (
        <p className="mt-2 text-sm">
          <span className="font-semibold">{t`Abandoned uploads:`}</span>
          {` ${preview.abandoned_upload_candidates} never-used uploads are eligible.`}
          {preview.abandoned_upload_has_more ? t` Cleanup continues in bounded batches.` : ""}
          {t` Late-write receipts: ${preview.late_write_receipts} (${preview.late_write_receipts_due} due).`}
        </p>
      ) : null}
    </div></SettingsRow>
  );
}
