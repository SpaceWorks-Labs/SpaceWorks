import { t } from "@lingui/core/macro";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { ScopePicker, useScopeOptions } from "./NotificationDestinations";
import {
  type DestinationScope,
  type RecipientKind,
  type RecipientRule,
  type RecipientRulesResponse,
  EMPTY_SCOPE,
} from "./notificationDestinationTypes";

export type Draft = {
  kind: RecipientKind;
  role_id: number | null;
  user_id: number | null;
  scope: DestinationScope;
};

export function EventRecipients({
  data,
  delegated,
  event,
  feature,
  makerspaceId,
  options,
  path,
}: {
  data: RecipientRulesResponse;
  delegated: boolean;
  event: string;
  feature: string;
  makerspaceId: number;
  options: ReturnType<typeof useScopeOptions>;
  path: string;
}) {
  const queryClient = useQueryClient();
  const saved = useMemo(
    () => data.rules.filter((rule) => rule.feature === feature && rule.event === event),
    [data.rules, event, feature],
  );
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [error, setError] = useState("");
  const rules = drafts ?? saved.map(toDraft);
  const marker = data.managed_policy_markers.find(
    (item) => item.feature === feature && item.event === event,
  );
  const hasUnscopedRule = delegated && rules.some((rule) => scopeCount(rule.scope) === 0);

  const save = useMutation({
    mutationFn: (next: Draft[]) =>
      staffRequest<RecipientRulesResponse>(path, {
        method: "PUT",
        body: JSON.stringify({ feature, event, rules: next }),
      }),
    onSuccess: () => {
      setDrafts(null);
      queryClient.invalidateQueries({
        queryKey: ["notification-recipient-rules", makerspaceId],
      });
    },
    onError: (err: unknown) =>
      setError(err instanceof Error ? err.message : t`Could not save recipients.`),
  });

  const update = (next: Draft[]) => {
    setDrafts(next);
    setError("");
  };

  return (
    <div className="mt-3 grid gap-2 rounded-md border border-line bg-bg p-3">
      {rules.length === 0 ? (
        <p className="text-sm text-muted">
          {delegated
            ? t`No recipient is selected in your scoped partition.`
            : t`Nobody selected — everyone whose role covers this area is notified.`}
        </p>
      ) : null}
      {marker ? (
        <p className="text-sm text-muted">
          {/* Deliberately names no author. A hidden remainder used to be a Space
              Manager's row by construction; a shared requester/members row can now hold
              another maintainer's links too, so claiming a manager wrote it would be a
              statement about a colleague that is often false. */}
          {t`Another policy also applies to this event, scoped outside your machines. Its recipients and scope are hidden; your changes will not replace it.`}</p>
      ) : null}

      {rules.map((rule, index) => (
        <div className="grid gap-2 border-b border-line pb-2 last:border-0" key={index}>
          <RecipientTarget
            data={data}
            staffOnly={STAFF_ONLY_FEATURES.has(feature)}
            index={index}
            rule={rule}
            rules={rules}
            update={update}
          />
          <ScopePicker
            onChange={(scope) =>
              update(rules.map((item, position) => position === index ? { ...item, scope } : item))
            }
            options={options}
            scopeRequired={delegated}
            scope={rule.scope}
          />
        </div>
      ))}

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {hasUnscopedRule ? (
        <p className="text-sm text-danger">
          {t`Each delegated rule needs at least one machine or machine type.`}</p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          className="desk-button"
          onClick={() => update([
            ...rules,
            { kind: "role", role_id: null, user_id: null, scope: EMPTY_SCOPE },
          ])}
          type="button"
        >
          {t`Add recipient`}</button>
        <SettingsEditorActions dirty={drafts !== null} onDiscard={() => { setDrafts(null); setError(""); }} pending={save.isPending} disabled={save.isPending || drafts === null || hasUnscopedRule} onSave={() => save.mutate(rules)} />

      </div>
    </div>
  );
}

/** Families whose selection names staff only: the member's own notices are not chosen here (decision 343). */
export const STAFF_ONLY_FEATURES = new Set(["printing"]);

export function RecipientTarget({ data, index, rule, rules, update, staffOnly = false }: {
  data: RecipientRulesResponse;
  staffOnly?: boolean;
  index: number;
  rule: Draft;
  rules: Draft[];
  update: (next: Draft[]) => void;
}) {
  const replace = (fields: Partial<Draft>) =>
    update(rules.map((item, position) => position === index ? { ...item, ...fields } : item));
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        aria-label={t`Recipient ${index + 1} type`}
        className="desk-input"
        onChange={(changed) => replace({
          kind: changed.target.value as RecipientKind,
          role_id: null,
          user_id: null,
        })}
        value={rule.kind}
      >
        <option value="role">{t`A role`}</option>
        <option value="user">{t`A named member`}</option>
        {staffOnly ? null : <option value="members">{t`All members`}</option>}
        {staffOnly ? null : <option value="requester">{t`The person it is about`}</option>}
      </select>
      {rule.kind === "role" ? (
        <select
          aria-label={t`Recipient ${index + 1} role`}
          className="desk-input"
          onChange={(changed) => replace({ role_id: Number(changed.target.value) })}
          value={rule.role_id ?? ""}
        >
          <option value="">{t`Choose a role…`}</option>
          {data.roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
        </select>
      ) : null}
      {rule.kind === "user" ? (
        <select
          aria-label={t`Recipient ${index + 1} member`}
          className="desk-input"
          onChange={(changed) => replace({ user_id: Number(changed.target.value) })}
          value={rule.user_id ?? ""}
        >
          <option value="">{t`Choose a member…`}</option>
          {data.members.map((member) => (
            <option key={member.id} value={member.id}>{member.username}</option>
          ))}
        </select>
      ) : null}
      <button
        className="desk-button-danger ml-auto"
        onClick={() => update(rules.filter((_, position) => position !== index))}
        type="button"
      >
        {t`Remove`}</button>
    </div>
  );
}

function toDraft(rule: RecipientRule): Draft {
  return {
    kind: rule.kind,
    role_id: rule.role_id,
    user_id: rule.user_id,
    scope: rule.scope ?? EMPTY_SCOPE,
  };
}

function scopeCount(scope: DestinationScope) {
  return scope.machine_type_ids.length + scope.machine_ids.length + scope.category_ids.length;
}
