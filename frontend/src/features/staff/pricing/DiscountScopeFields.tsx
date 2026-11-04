import { COMPONENT_LABELS, domainLabel, type PricingDomain } from "./pricingApi";
import type { DiscountForm } from "./discountForm";

const toggle = <T,>(list: T[], value: T, on: boolean) => (on ? [...list, value] : list.filter(item => item !== value));

/** Where the discount applies: areas (none ticked = every area) and, optionally, named prices only. */
export function DiscountScopeFields({ domains, form, onChange }: {
  domains: PricingDomain[]; form: DiscountForm; onChange: (patch: Partial<DiscountForm>) => void;
}) {
  const scoped = form.domains.length ? form.domains : domains;
  const components = scoped.flatMap(domain => COMPONENT_LABELS[domain].map(([key, label]) => ({ key, label, domain })));
  const setDomains = (next: PricingDomain[]) => {
    const allowed = new Set((next.length ? next : domains).flatMap(domain => COMPONENT_LABELS[domain].map(([key]) => key)));
    onChange({ domains: next, components: form.components.filter(key => allowed.has(key)) });
  };
  return <div className="grid gap-4">
    <fieldset className="grid gap-1">
      <legend className="text-sm font-semibold text-ink">Areas</legend>
      <p className="text-xs text-muted">Leave all unticked to apply in every area.</p>
      <div className="flex flex-wrap gap-x-5">
        {domains.map(domain => <label key={domain} className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4" checked={form.domains.includes(domain)}
            onChange={event => setDomains(toggle(form.domains, domain, event.target.checked))} />{domainLabel(domain)}</label>)}
      </div>
    </fieldset>
    <fieldset className="grid gap-1">
      <legend className="text-sm font-semibold text-ink">Only these prices (optional)</legend>
      <p className="text-xs text-muted">Leave all unticked to discount rentals, machine time, bookings, registrations and dues.
        Tick a deposit or a fee to discount it too; ticking any price limits the discount to the ticked ones.</p>
      <div className="grid gap-x-5 sm:grid-cols-2">
        {components.map(({ key, label, domain }) => <label key={`${domain}-${key}`} className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4" checked={form.components.includes(key)}
            onChange={event => onChange({ components: toggle(form.components, key, event.target.checked) })} />
          {label}<span className="text-muted"> · {domainLabel(domain)}</span></label>)}
      </div>
    </fieldset>
  </div>;
}
