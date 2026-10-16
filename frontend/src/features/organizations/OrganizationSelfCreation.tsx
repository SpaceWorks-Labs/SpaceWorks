import { useState } from "react";
import { Link } from "react-router-dom";
import { useTenant } from "../../lib/tenant";
import { useCreateOwnOrganization, useOrganizationCreationPolicy } from "./organizationSelfServiceApi";

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
  if (policy.isLoading) return <p role="status">Loading organization creation options…</p>;
  if (policy.error) return <p role="alert" className="text-danger">{policy.error.message}</p>;
  if (!policy.data?.enabled) return null;
  return <section className="grid gap-3 rounded border border-line p-4" aria-labelledby="self-organization-heading">
    <h2 id="self-organization-heading" className="title-section">Create your organization</h2>
    <p className="text-sm text-muted">Create a private organization profile and invite other governors. Makerspace links require platform approval. Creation is limited to {policy.data.max_per_day} per day and {policy.data.max_owned} owned organizations.</p>
    {!policy.data.eligible ? <p>{policy.data.reason}</p> : <form className="grid gap-3" onSubmit={event => {
      event.preventDefault();
      create.mutate({ name: name.trim(), slug: slug.trim() }, { onSuccess: row => {
        setName(""); setSlug(""); onCreated?.(row.id);
      } });
    }}>
      <label className="grid gap-1">Organization name<input className="desk-input" required maxLength={200} value={name} onChange={event => setName(event.target.value)} /></label>
      <label className="grid gap-1">Organization slug<input className="desk-input" required maxLength={50} pattern="[-a-zA-Z0-9_]+" value={slug} onChange={event => setSlug(event.target.value)} /></label>
      <button className="desk-button-primary" disabled={create.isPending || !name.trim() || !slug.trim()}>{create.isPending ? "Creating…" : "Create private organization"}</button>
    </form>}
    {create.error ? <p role="alert" className="text-danger">{create.error.message}</p> : null}
    {create.isSuccess ? <p role="status">Organization created. <Link className="underline" to="/admin/organizations?sign-in=staff">Sign in to manage your organization</Link></p> : null}
  </section>;
}
