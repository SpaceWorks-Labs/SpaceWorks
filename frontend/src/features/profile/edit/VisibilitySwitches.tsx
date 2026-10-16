import type { FamilyFlags } from "../publicProfileApi";
import { fieldError, usePatchPublication } from "./profileEditApi";

const FAMILIES: { key: keyof FamilyFlags; label: string; helper: string }[] = [
  { key: "show_activity_graph", label: "Activity graph", helper: "Daily counts only, plus your GitHub graph if you linked one." },
  { key: "show_events", label: "Events", helper: "Public events you attended or hosted." },
  { key: "show_speaking", label: "Speaking", helper: "Sessions you spoke at, on the activity graph." },
  { key: "show_projects", label: "Projects", helper: "Projects you mark public below." },
  { key: "show_machine_activity", label: "Machine activity", helper: "Completed machine jobs, on the activity graph." },
  { key: "show_bookings", label: "Bookings", helper: "Completed bookings, on the activity graph." },
  { key: "show_loans", label: "Loans", helper: "Hardware you borrowed and returned, on the activity graph." },
];

/** Each family is its own consent. All start off; a switch saves on its own, no form submit. */
export function VisibilitySwitches({ makerspaceId, flags }: { makerspaceId: number; flags: Partial<FamilyFlags> }) {
  const patch = usePatchPublication(makerspaceId);
  const pendingKey = patch.isPending ? Object.keys(patch.variables ?? {})[0] : undefined;
  return <fieldset className="grid gap-1">
    <legend className="sr-only">What your public page shows</legend>
    {FAMILIES.map(family => {
      const checked = Boolean(flags[family.key]);
      const id = `profile-family-${family.key}-${makerspaceId}`;
      return <label key={family.key} htmlFor={id} className="flex min-h-11 cursor-pointer items-start gap-3 rounded-control py-2 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus">
        <input id={id} type="checkbox" role="switch" className="mt-0.5 h-5 w-5 accent-accent" checked={checked}
          disabled={patch.isPending} aria-describedby={`${id}-helper`}
          onChange={() => patch.mutate({ [family.key]: !checked })} />
        <span className="grid">
          <span className="text-sm font-semibold text-ink">{family.label}{pendingKey === family.key ? " · Saving…" : ""}</span>
          <span id={`${id}-helper`} className="text-sm text-muted">{family.helper}</span>
        </span>
      </label>;
    })}
    {patch.error ? <p role="alert" className="text-sm text-danger">{fieldError(patch.error, "detail")}</p> : null}
  </fieldset>;
}
