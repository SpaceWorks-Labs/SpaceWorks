import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Callout, DetailDrawer, ErrorText, KeyValueCard, RelativeTime, Skeleton } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import type { HealthCard } from "../platformSpaces/spacesApi";
import { keyActions } from "./keyCopy";
import { KeyJobsList } from "./KeyJobsList";
import { useRotateKey, useSpaceKeys, type KeyAction } from "./spaceKeysApi";
import { StaleArchivesList } from "./StaleArchivesList";
import { TypedConfirmDialog } from "./TypedConfirmDialog";

/** One space's encryption keys: versions, rotations with live progress, and its archives on a retired backup key (#190). */
export function SpaceKeysDrawer({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const keys = useSpaceKeys(card.id);
  const rotate = useRotateKey(card.id);
  const [action, setAction] = useState<KeyAction | null>(null);
  const data = keys.data;
  const chosen = keyActions().find(row => row.action === action);
  return <DetailDrawer open title={t`Keys of ${card.name}`} onClose={onClose}>
    {keys.isLoading ? <Skeleton className="h-40 w-full" /> : keys.isError || !data
      ? <ErrorText resource={t`this space's keys`} onRetry={() => { void keys.refetch(); }} /> : <div className="grid gap-6">
      {data.rls_mode !== "enforce" ? <Callout size="inline" tone="warn" lead={`Row-level security is ${data.rls_mode}.`}
        body={t`The database does not yet stop a cross-space read on this deployment.`} /> : null}
      <KeyValueCard title={t`Keys`} items={[
        { label: t`Data key version`, value: data.active_dek_version ?? "None yet" },
        { label: t`Search key version`, value: data.search_key_version ?? "Deployment key" },
        { label: t`Browser key last rotated`, value: data.publishable_key_rotated_at
          ? <RelativeTime date={data.publishable_key_rotated_at} exact /> : "Never" },
        ...(data.previous_publishable_key_valid_until ? [{ label: t`Old browser key works until`,
          value: <RelativeTime date={data.previous_publishable_key_valid_until} exact /> }] : []),
      ]} />
      <section aria-labelledby="space-key-actions" className="grid gap-3">
        <h3 id="space-key-actions" className="title-panel">{t`Rotate`}</h3>
        <p className="text-sm text-muted">{t`Each one asks you to type `}<code>{card.slug}</code> {t` and confirm your sign-in. It is recorded in this space's audit log.`}</p>
        <div className="flex flex-wrap gap-2">{keyActions().map(row => {
          const blocked = Boolean(data.running) && row.action !== "rotate_publishable_key";
          const off = Boolean(row.needsPii) && !data.pii_encryption_enabled;
          return <button key={row.action} type="button" className={row.action === "emergency_rekey" ? "desk-button-danger-outline" : "desk-button"}
            disabled={blocked || off} title={off ? t`Scoped encryption is off on this deployment.` : blocked ? t`A key job is still running.` : undefined}
            onClick={() => { rotate.reset(); setAction(row.action); }}>{row.label}…</button>;
        })}</div>
      </section>
      <section aria-labelledby="space-key-jobs" className="grid gap-3">
        <h3 id="space-key-jobs" className="title-panel">{t`Key jobs`}</h3>
        <KeyJobsList jobs={data.jobs} />
      </section>
      <section aria-labelledby="space-key-archives" className="grid gap-3">
        <h3 id="space-key-archives" className="title-panel">{t`Archives on a retired backup key`}</h3>
        <StaleArchivesList card={card} rows={data.stale_archives} />
      </section>
    </div>}
    {chosen ? <TypedConfirmDialog title={chosen.label} confirmLabel={chosen.label} expected={card.slug} what="space's web address name"
      message={chosen.message} pending={rotate.isPending} error={rotate.error} onCancel={() => setAction(null)}
      onConfirm={typed => rotate.mutate({ action: chosen.action, confirm_slug: typed },
        { onSuccess: () => { toast(t`${chosen.label}: started.`); setAction(null); } })} /> : null}
  </DetailDrawer>;
}
