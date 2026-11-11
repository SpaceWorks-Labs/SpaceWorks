import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { memberKits, staffContextKits, type SafeKit } from "./equipmentKitsApi";
import { PagePager } from "../../components/ui";

type KitLine = SafeKit["lines"][number];

function lineSentence(line: KitLine) {
  const name = line.display_name;
  const quantity = line.quantity_per_person;
  return line.kind === "consumable"
    ? t`${name}: ${quantity} per person, used up`
    : t`${name}: ${quantity} per person, returned after use`;
}

export function KitChoice({ scope, slug, staff, value, onChange, disabled, consumableOnly = false }: {
  scope: string; slug?: string; staff?: { tenant: number; domain: "event" | "booking"; resource: number };
  value: SafeKit | null; onChange: (value: SafeKit | null) => void; disabled: boolean; consumableOnly?: boolean;
}) {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["equipment-kits", scope, page], retry: false,
    enabled: Boolean(slug || staff), queryFn: () => staff ? staffContextKits(staff.tenant, staff.domain, staff.resource, page) : memberKits(slug!, page) });
  const kits = (query.data?.results ?? []).filter(kit => !consumableOnly || kit.lines.length > 0 && kit.lines.every(line => line.kind === "consumable"));
  const choice = (chosen: boolean) => (chosen ? "desk-button-primary" : "desk-button");
  return <fieldset disabled={disabled} className="grid gap-2">
    <legend className="text-sm font-semibold text-ink">{t`Choose a kit (optional)`}</legend>
    <div className="flex flex-wrap gap-2">
      <button type="button" className={choice(!value)} aria-pressed={!value} onClick={() => onChange(null)}>{t`Choose individual items`}</button>
      {query.isSuccess ? kits.map(kit => {
        const chosen = value?.id === kit.id && value.version === kit.version;
        return <button type="button" key={kit.id} className={choice(chosen)} aria-pressed={chosen} onClick={() => onChange(kit)}>{kit.name}</button>;
      }) : null}
    </div>
    {query.isPending ? <p className="text-sm text-muted" role="status">{t`Loading kits…`}</p> : null}
    {query.isError ? <p className="text-sm text-muted" role="status">{t`Kits are unavailable for your access.`}</p> : null}
    {query.isSuccess && !kits.length ? <p className="text-sm text-muted">{consumableOnly ? t`No consumable kits are available here.` : t`No kits are available here.`}</p> : null}
    {query.isSuccess ? <PagePager page={page} setPage={setPage} next={query.data.next} /> : null}
    {value ? <ul className="grid gap-1 text-sm text-muted" aria-label={t`Kit contents`}>{value.lines.map(line => <li key={line.product_id}>{lineSentence(line)}</li>)}</ul> : null}
  </fieldset>;
}
