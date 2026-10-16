import { useId, useState } from "react";
import { StructuredApiError } from "../../../../lib/api";
import { useOrganizations } from "../../organizationsApi";
import type { MakerspaceForm } from "./types";

export function organizationFieldErrors(error: unknown) {
  const body: Record<string, unknown> = error instanceof StructuredApiError ? error.body : {};
  const fields = body.fields && typeof body.fields === "object" ? body.fields as Record<string, unknown> : body;
  const message = (value: unknown) => typeof value === "string" ? value : Array.isArray(value) ? value.filter(item => typeof item === "string").join(" ") : "";
  return { organization_id: message(fields.organization_id), organization_name: message(fields.organization_name) };
}

export function OrganizationPicker({ form, error, onChange }: {
  form: MakerspaceForm; error: unknown; onChange: (form: MakerspaceForm) => void;
}) {
  const id = useId();
  const [search, setSearch] = useState("");
  const errors = organizationFieldErrors(error);
  const describedBy = [errors.organization_id ? `${id}-existing-error` : "", errors.organization_name ? `${id}-name-error` : ""].filter(Boolean).join(" ") || undefined;
  return <fieldset className="grid gap-3" aria-describedby={describedBy}>
    <legend className="eyebrow">Organization (required)</legend>
    <p className="text-xs text-muted">Choose an active organization to own this makerspace, or create a new one.</p>
    <label htmlFor={`${id}-search`} className="grid gap-1">
      <span className="eyebrow">Search organizations</span>
      <input id={`${id}-search`} type="search" className="desk-input w-full" value={search} onChange={event => setSearch(event.target.value)} aria-describedby={errors.organization_id ? `${id}-existing-error` : undefined} />
    </label>
    {form.organization && form.organization !== "new" ? <p className="text-sm" role="status">Selected organization: {form.organization.name}</p> : null}
    <OrganizationResults key={search.trim()} search={search.trim()} page={1} id={id} selected={form.organization} errorId={errors.organization_id ? `${id}-existing-error` : undefined} onSelect={organization => onChange({ ...form, organization })} />
    {errors.organization_id ? <p id={`${id}-existing-error`} role="alert" className="text-sm text-danger">{errors.organization_id}</p> : null}
    <label htmlFor={`${id}-new`} className="flex min-h-11 items-center gap-2">
      <input id={`${id}-new`} type="radio" name={`${id}-organization`} checked={form.organization === "new"} onChange={() => onChange({ ...form, organization: "new" })} aria-describedby={errors.organization_name ? `${id}-name-error` : undefined} />
      New organization
    </label>
    {form.organization === "new" ? <label htmlFor={`${id}-name`} className="grid gap-1">
      <span className="eyebrow">New organization name</span>
      <input id={`${id}-name`} className="desk-input w-full" required maxLength={200} value={form.organization_name ?? form.name} onChange={event => onChange({ ...form, organization_name: event.target.value })} aria-invalid={Boolean(errors.organization_name)} aria-describedby={errors.organization_name ? `${id}-name-error` : undefined} />
    </label> : null}
    {errors.organization_name ? <p id={`${id}-name-error`} role="alert" className="text-sm text-danger">{errors.organization_name}</p> : null}
  </fieldset>;
}

function OrganizationResults({ search, page, id, selected, errorId, onSelect }: {
  search: string; page: number; id: string; selected: MakerspaceForm["organization"]; errorId?: string;
  onSelect: (organization: { id: number; name: string }) => void;
}) {
  const organizations = useOrganizations({ page, search, active: true });
  const [expanded, setExpanded] = useState(false);
  return <div className="grid gap-2">
    {organizations.isLoading ? <p role="status" className="text-sm text-muted">Loading organizations…</p> : null}
    {organizations.error ? <div role="alert" className="text-sm text-danger">{organizations.error.message} <button type="button" className="desk-button" onClick={() => organizations.refetch()}>Retry</button></div> : null}
    {organizations.data?.results.length === 0 && page === 1 ? <p role="status" className="text-sm text-muted">No active organizations found.</p> : null}
    {organizations.data?.results.map(organization => <label key={organization.id} htmlFor={`${id}-${organization.id}`} className="flex min-h-11 items-center gap-2">
      <input id={`${id}-${organization.id}`} type="radio" name={`${id}-organization`} checked={typeof selected === "object" && selected.id === organization.id} onChange={() => onSelect({ id: organization.id, name: organization.name })} aria-invalid={Boolean(errorId)} aria-describedby={errorId} />
      {organization.name} <span className="text-xs text-muted">{organization.slug}</span>
    </label>)}
    {expanded ? <OrganizationResults search={search} page={page + 1} id={id} selected={selected} errorId={errorId} onSelect={onSelect} /> : organizations.data?.next ? <button type="button" className="desk-button" onClick={() => setExpanded(true)}>Load more</button> : null}
  </div>;
}
