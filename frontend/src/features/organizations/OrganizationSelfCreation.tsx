import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorText, SettingsRow } from "../../components/ui";
import { useTenant } from "../../lib/tenant";
import { useCreateOwnOrganization, useOrganizationCreationPolicy } from "./organizationSelfServiceApi";

/**
 * Whether the self-creation section has anything to show: the central origin and a policy that is on.
 * A policy that failed to load still counts, so its error stays visible. Callers use this to drop the
 * section heading (or the "Create organization" entry point) instead of rendering an empty one.
 */
export function useOrganizationSelfCreationVisible(active = true) {
  const tenant = useTenant();
  const central = active && tenant.mode === "central";
  const policy = useOrganizationCreationPolicy(central);
  return central && (Boolean(policy.error) || policy.data?.enabled === true);
}

/** Section rows: the caller's settings section supplies the heading. */
export function OrganizationSelfCreation({ onCreated }: { onCreated?: (id: number) => void }) {
  const tenant = useTenant();
  // Global organization operations are unavailable on tenant-bound origins.
  return tenant.mode === "central" ? <EligibleOrganizationSelfCreation onCreated={onCreated} /> : null;
}

function EligibleOrganizationSelfCreation({ onCreated }: { onCreated?: (id: number) => void }) {
  const policy = useOrganizationCreationPolicy();
  const create = useCreateOwnOrganization();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  if (policy.isLoading) return <p role="status" className="py-5 text-sm text-muted">Loading organization creation options…</p>;
  if (policy.error) return <div className="py-5"><ErrorText message={policy.error.message} /></div>;
  if (!policy.data?.enabled) return null;
  return <div className="grid divide-y divide-line">
    <p className="pb-5 text-sm text-muted">Create a private organization profile and invite other governors. Makerspace links require platform approval. Creation is limited to {policy.data.max_per_day} per day and {policy.data.max_owned} owned organizations.</p>
    {!policy.data.eligible ? <p className="py-5 text-sm text-ink">{policy.data.reason}</p> : <form className="grid divide-y divide-line" onSubmit={event => {
      event.preventDefault();
      create.mutate({ name: name.trim(), slug: slug.trim() }, { onSuccess: row => {
        setName(""); setSlug(""); onCreated?.(row.id);
      } });
    }}>
      <SettingsRow label="Organization name" htmlFor="self-organization-name">
        <input id="self-organization-name" className="desk-input w-full" required maxLength={200} value={name} onChange={event => setName(event.target.value)} />
      </SettingsRow>
      <SettingsRow label="Organization slug" htmlFor="self-organization-slug" helper="Letters, numbers, hyphens and underscores.">
        <input id="self-organization-slug" className="desk-input w-full" required maxLength={50} pattern="[-a-zA-Z0-9_]+" value={slug} onChange={event => setSlug(event.target.value)} />
      </SettingsRow>
      <div className="flex justify-end py-5"><button className="desk-button-primary w-full sm:w-auto" disabled={create.isPending || !name.trim() || !slug.trim()}>{create.isPending ? "Creating…" : "Create private organization"}</button></div>
    </form>}
    {create.error ? <div className="py-5"><ErrorText message={create.error.message} /></div> : null}
    {create.isSuccess ? <p role="status" className="py-5 text-sm text-ink">Organization created. <Link className="font-semibold text-brand-ink underline-offset-4 hover:underline" to="/admin/organizations?sign-in=staff">Sign in to manage your organization</Link></p> : null}
  </div>;
}
