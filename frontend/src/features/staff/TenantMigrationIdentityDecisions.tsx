import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listImportIdentities,
  submitIdentityDecisions,
  tenantMigrationKeys,
  type ImportIdentityDecision,
  type ImportJob,
} from "./tenantMigrationApi";
import { ErrorText } from "./tenantMigrationUi";
import { BoxArt } from "../../components/BoxSpinner";

type DraftDecision = Omit<ImportIdentityDecision, "source_user_id">;

const defaultDecision: DraftDecision = {
  identity_resolution: "create_walk_in",
  membership_disposition: "import_membership",
  target_user_id: null,
};

export function TenantMigrationIdentityDecisions({ job, active = true }: { job: ImportJob; active?: boolean }) {
  const client = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, DraftDecision>>({});
  const identities = useQuery({
    queryKey: tenantMigrationKeys.identities(job.id),
    queryFn: () => listImportIdentities(job.id),
    enabled: job.status === "awaiting_identity" || job.status === "ready",
  });
  const submit = useMutation({
    mutationFn: () => submitIdentityDecisions(job.id, {
      decisions: (identities.data ?? []).map((identity) => ({
        source_user_id: String(identity.id),
        ...(drafts[String(identity.id)] ?? defaultDecision),
      })),
    }),
    onSuccess: (next) => {
      client.setQueryData(tenantMigrationKeys.import(job.id), next);
      client.invalidateQueries({ queryKey: tenantMigrationKeys.imports });
    },
  });
  const decisionFor = (id: number) => drafts[String(id)] ?? defaultDecision;
  const choicesAvailable = job.status === "awaiting_identity" || Boolean(submit.data);
  const update = (id: number, patch: Partial<DraftDecision>) => setDrafts((current) => ({
    ...current,
    [String(id)]: { ...decisionFor(id), ...patch },
  }));

  if (!active) return null;
  return (
    <section className="mt-3 rounded-md border border-line bg-bg p-3" aria-labelledby={`identity-title-${job.id}`}>
      <h4 className="title-section" id={`identity-title-${job.id}`}>{t`Per-person identity decisions`}</h4>
      <p className="mt-1 text-sm text-muted">{t`Review every mapping before starting materialization. Linking preserves an existing target account; walk-in creates a non-login identity for attribution.`}</p>
      {identities.isLoading ? <p className="mt-3 text-sm text-muted">{t`Reading archived identities…`}</p> : null}
      <ErrorText error={identities.error} />
      <div className="mt-3 grid gap-3">
        {(identities.data ?? []).map((identity) => {
          const decision = decisionFor(identity.id);
          return (
            <article className="rounded-md border border-line bg-surface p-3" key={identity.id}>
              <p className="font-semibold text-ink">{identity.display_name || identity.username}</p>
              <p className="break-words text-xs text-muted">{identity.email || t`No email`} · {identity.phone || t`No phone`} {t` · source user ${identity.id}`}</p>
              {choicesAvailable ? <div className="mt-2 grid gap-3 @2xl:grid-cols-3">
                <label className="text-sm text-ink">
                  {t`Identity resolution`}<select
                    aria-label={t`Identity resolution for ${identity.display_name || identity.username}`}
                    className="desk-input mt-1 w-full"
                    value={decision.identity_resolution}
                    onChange={(event) => update(identity.id, {
                      identity_resolution: event.target.value as DraftDecision["identity_resolution"],
                      target_user_id: event.target.value === "link_existing" ? decision.target_user_id : null,
                    })}
                  >
                    <option value="create_walk_in">{t`Create walk-in`}</option>
                    <option value="link_existing">{t`Link existing account`}</option>
                  </select>
                </label>
                {decision.identity_resolution === "link_existing" ? (
                  <label className="text-sm text-ink">
                    {t`Target user ID`}<input
                      aria-label={t`Target user ID for ${identity.display_name || identity.username}`}
                      className="desk-input mt-1 w-full"
                      min="1"
                      type="number"
                      value={decision.target_user_id ?? ""}
                      onChange={(event) => update(identity.id, { target_user_id: event.target.value ? Number(event.target.value) : null })}
                    />
                  </label>
                ) : null}
                <label className="text-sm text-ink">
                  {t`Membership`}<select
                    aria-label={t`Membership for ${identity.display_name || identity.username}`}
                    className="desk-input mt-1 w-full"
                    value={decision.membership_disposition}
                    onChange={(event) => update(identity.id, { membership_disposition: event.target.value as DraftDecision["membership_disposition"] })}
                  >
                    <option value="import_membership">{t`Import membership`}</option>
                    <option value="no_membership">{t`Do not import membership`}</option>
                  </select>
                </label>
              </div> : null}
            </article>
          );
        })}
      </div>
      {job.status === "awaiting_identity" ? (
        <button
          className="desk-button-primary mt-3"
          type="button"
          disabled={submit.isPending || !identities.data || identities.data.some((identity) => {
            const decision = decisionFor(identity.id);
            return decision.identity_resolution === "link_existing" && !decision.target_user_id;
          })}
          onClick={() => submit.mutate()}
        >
          {submit.isPending ? <><BoxArt size={16} mono />{t`Submitting decisions…`}</> : t`Submit all identity decisions`}
        </button>
      ) : submit.data ? <p className="mt-3 text-sm font-semibold text-success-ink">{t`Identity decisions accepted. Review the choices above before running the import.`}</p> : (
        <p className="mt-3 text-sm text-warn-ink">{t`Decisions were accepted in an earlier session. The API returns the exact people but not the saved mapping choices; verify the prior review record before running.`}</p>
      )}
      <ErrorText error={submit.error} field="decisions" />
    </section>
  );
}
