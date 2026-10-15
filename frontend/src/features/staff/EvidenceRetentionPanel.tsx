import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState, type FormEvent } from "react";

import { AbandonedUploadCleanupSection } from "./AbandonedUploadCleanupSection";

import { StructuredApiError } from "../../lib/api";
import {
  useEvidenceRetentionPolicy,
  useEvidenceRetentionPreview,
  useUpdateEvidenceRetention,
} from "./evidenceRetentionApi";


const bytes = (value: number) => new Intl.NumberFormat(undefined, {
  style: "unit",
  unit: "megabyte",
  maximumFractionDigits: 1,
}).format(value / 1_048_576);

const errorText = (error: unknown) =>
  error instanceof StructuredApiError
    ? error.detail ?? error.message
    : "Unable to load evidence retention settings.";

export function EvidenceRetentionPanel({ makerspaceId }: { makerspaceId: number }) {
  const policy = useEvidenceRetentionPolicy(makerspaceId);
  const update = useUpdateEvidenceRetention(makerspaceId);
  const effectiveDays = policy.data?.effective_days ?? 0;
  const preview = useEvidenceRetentionPreview(
    makerspaceId,
    effectiveDays,
    Boolean(policy.data),
  );
  const [days, setDays] = useState("");
  const [daysTouched, setDaysTouched] = useState(false);

  useEffect(() => {
    if (policy.data) { setDays(String(policy.data.effective_days)); setDaysTouched(false); }
  }, [policy.data?.effective_days, policy.data?.override_days]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({ object_retention_days: Number(days) });
  };

  if (policy.isLoading) return <SettingsQueryState query={policy} resource="evidence retention" />;
  if (policy.error) return <SettingsQueryState query={policy} resource="evidence retention" />;
  if (!policy.data) return null;

  return (
    <><SettingsRow label="Evidence photo retention" helper="Attached evidence rows are immutable and are never deleted; audit history is append-only. Stored image bytes expire after the effective window."><div className="grid min-w-0 gap-4">


      <p className="mt-2 text-sm font-semibold text-warn-ink" role="note">
        Expiry is irreversible in live storage; older backups may still contain historical photos.
      </p>
      <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={submit}>
        <label className="grid gap-1 text-sm font-semibold text-ink">
          Retention days
          <input
            className="desk-input w-40"
            type="number"
            min="30"
            max="3650"
            value={days}
            onChange={(event) => { setDays(event.target.value); setDaysTouched(true); }}
            required
          />
        </label>
        <SettingsEditorActions dirty={days !== String(effectiveDays) || (daysTouched && policy.data.override_days === null)} onDiscard={() => { setDays(String(effectiveDays)); setDaysTouched(false); }} pending={update.isPending} disabled={update.isPending} />
        <button
          className="desk-button"
          type="button"
          disabled={update.isPending || policy.data.override_days === null}
          onClick={() => update.mutate({ object_retention_days: null })}
        >
          Use platform default
        </button>
      </form>
      <p className="mt-2 text-xs text-muted">
        {policy.data.override_days === null
          ? `Inherited platform default: ${policy.data.platform_default_days} days.`
          : `Tenant override: ${policy.data.override_days} days (platform default ${policy.data.platform_default_days}).`}
        {` Automatic expiry is ${policy.data.object_expiry_enabled ? "enabled" : "disabled"}.`}
      </p>
      {update.error ? <p className="mt-2 text-sm text-danger" role="alert">{errorText(update.error)}</p> : null}
      <SettingsQueryState query={preview} resource="retention preview"><div className="mt-3 rounded-lg border border-line bg-surface p-3 text-sm">
        {preview.isLoading ? <span className="text-muted">Calculating preview…</span> : null}
        {preview.error ? <span className="text-danger">{errorText(preview.error)}</span> : null}
        {preview.data ? (
          <p>
            <span className="font-semibold">Preview:</span>{` ${preview.data.object_candidates} photo objects (${bytes(preview.data.candidate_bytes)}) are eligible as of ${new Date(preview.data.as_of).toLocaleString()}.`}
            {preview.data.has_more ? " The first sweep will continue in bounded batches." : ""}
          </p>
        ) : null}
      </div></SettingsQueryState>

    </div></SettingsRow><AbandonedUploadCleanupSection
        policy={policy.data}
        preview={preview.data}
        pending={update.isPending}
        onChange={(changes) => update.mutate(changes)}
      /></>
  );
}
