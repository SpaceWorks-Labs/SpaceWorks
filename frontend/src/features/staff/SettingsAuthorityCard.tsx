import { useState } from "react";
import { ShieldCheck } from "lucide-react";

import { ErrorBlock } from "../../components/ui";
import {
  AUTHORITY_MODULES, MODULE_MANAGER_LABELS, type AuthorityModule, useSettingsGrants, useUpdateGrants,
} from "./settingsAuthorityApi";

/**
 * "Who can change settings" (#101, #128 C-11): the Space Manager gives one person at a time
 * control of a module's settings. Without a grant, that module's manager sees them read-only.
 * The Inventory Manager always sets loan length and renewals, with or without a grant.
 */
export function SettingsAuthorityCard({ makerspaceId }: { makerspaceId: number }) {
  const grants = useSettingsGrants(makerspaceId);
  const update = useUpdateGrants(makerspaceId);
  const [adding, setAdding] = useState<Partial<Record<AuthorityModule, string>>>({});
  if (grants.isLoading) return <p className="text-sm text-muted">Loading who can change settings…</p>;
  if (!grants.data) return <ErrorBlock error={grants.error ?? new Error("Couldn't load settings access.")}
    onRetry={() => { void grants.refetch(); }} />;
  const rows = grants.data.grants ?? [];
  const candidates = grants.data.candidates ?? {};
  const holders = (module: AuthorityModule) => rows.filter(row => row.module === module);
  const save = (module: AuthorityModule, ids: number[]) => update.mutate({ module, grantee_ids: ids });
  return <section aria-labelledby="settings-authority-title" className="grid min-w-0 gap-3 rounded-xl border border-line bg-surface p-4">
    <div className="flex min-w-0 items-start gap-3">
      <ShieldCheck aria-hidden="true" size={24} className="shrink-0 text-accent-ink" />
      <div className="grid min-w-0 gap-0.5">
        <h3 id="settings-authority-title" className="title-section">Who can change settings</h3>
        <p className="text-sm text-muted">You can change every setting. Give a module&apos;s manager control of that module&apos;s settings, one person at a time; without it they see the settings read-only. Inventory Managers always set loan length and renewals.</p>
      </div>
    </div>
    <ul className="grid min-w-0 gap-3">{AUTHORITY_MODULES.map(module => {
      const current = holders(module);
      const ids = current.map(row => row.grantee).filter((id): id is number => id !== null);
      const options = (candidates[module] ?? []).filter(person => !ids.includes(person.id));
      const selectId = `grant-${module}`;
      return <li key={module} className="grid min-w-0 gap-2 border-t border-line pt-3 first:border-0 first:pt-0">
        <span className="text-sm font-semibold text-ink">{MODULE_MANAGER_LABELS[module]}</span>
        {current.length ? <ul className="flex min-w-0 flex-wrap gap-2">{current.map(row => <li key={row.id}
          className="flex min-h-11 min-w-0 items-center gap-2 rounded-control border border-line px-3 text-sm text-ink">
          <span className="min-w-0 [overflow-wrap:anywhere]">{row.grantee_name || "Former account"}</span>
          <button type="button" className="desk-button-ghost" disabled={update.isPending}
            aria-label={`Remove ${row.grantee_name} from ${MODULE_MANAGER_LABELS[module]}`}
            onClick={() => save(module, ids.filter(id => id !== row.grantee))}>Remove</button>
        </li>)}</ul> : <p className="text-sm text-muted">Only you can change these.</p>}
        {options.length ? <div className="flex min-w-0 flex-wrap items-end gap-2">
          <label className="grid min-w-0 gap-1 text-sm text-ink" htmlFor={selectId}>Give control to
            <select id={selectId} className="desk-input min-w-0" value={adding[module] ?? ""}
              onChange={event => setAdding(value => ({ ...value, [module]: event.target.value }))}>
              <option value="">Choose a person</option>
              {options.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}
            </select>
          </label>
          <button type="button" className="desk-button" disabled={!adding[module] || update.isPending}
            onClick={() => { save(module, [...ids, Number(adding[module])]); setAdding(value => ({ ...value, [module]: "" })); }}>
            Give control</button>
        </div> : null}
      </li>;
    })}</ul>
    {update.error ? <p role="alert" className="text-sm text-danger">{update.error.message}</p> : null}
    {update.isSuccess ? <p role="status" className="text-sm text-muted">Settings access updated.</p> : null}
  </section>;
}
