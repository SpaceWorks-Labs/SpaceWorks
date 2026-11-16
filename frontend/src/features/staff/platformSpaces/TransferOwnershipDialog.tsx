import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "./ActionDialog";
import { useSpaceAction, type HealthCard, type TransferBody, type TransferResult } from "./spacesApi";

type Outcome = TransferBody["previous_outcome"];
const OUTCOMES: [Outcome, string][] = [
  ["keep_staff", "Keep them as staff with the roles below"],
  ["revoke", "Remove their staff access"],
  ["keep_manager", "Keep them as a second Space Manager"],
];
/** Built-in staff roles a previous manager may keep (never `space_manager`). */
export const STAFF_ROLES: [string, string][] = [
  ["inventory_manager", "Inventory Manager"], ["machine_manager", "Machine Manager"], ["event_manager", "Event Manager"],
  ["booking_manager", "Booking Manager"], ["handover", "Handover"], ["technician", "Technician"], ["shop_manager", "Shop Manager"],
  ["fundraising", "Fundraising"],
];

export function TransferOwnershipDialog({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [previous, setPrevious] = useState<number | null>(card.managers[0]?.membership_id ?? null);
  const [outcome, setOutcome] = useState<Outcome>("keep_staff");
  const [roles, setRoles] = useState<string[]>([]);
  const mutation = useSpaceAction<TransferResult>(card.id, "transfer-ownership", result => {
    toast(result.status === "invited"
      ? t`Invitation sent. The previous manager stays until the new manager accepts; then run the transfer again.`
      : t`Ownership transferred.`);
    onClose();
  });
  const needsRoles = previous !== null && outcome === "keep_staff";
  const canSubmit = /^\S+@\S+\.\S+$/.test(email.trim()) && (!needsRoles || roles.length > 0);
  const toggle = (slug: string) => setRoles(current => current.includes(slug) ? current.filter(item => item !== slug) : [...current, slug]);
  return <ActionDialog title={t`Transfer ownership`} confirmLabel={t`Transfer ownership`} pending={mutation.isPending} error={mutation.error}
    canSubmit={canSubmit} onCancel={onClose}
    message={t`The new Space Manager takes over ${card.name}. If the email has no account here yet, they are invited first.`}
    onSubmit={() => mutation.mutate({ email: email.trim(), previous_membership_id: previous,
      previous_outcome: outcome, previous_roles: needsRoles ? roles : [] } satisfies TransferBody)}>
    <Field label={t`New manager's email`}>
      <input className="desk-input" type="email" autoComplete="off" value={email} onChange={event => setEmail(event.target.value)} />
    </Field>
    <Field label={t`Current manager`}>
      <select className="desk-input" value={previous ?? ""} onChange={event => setPrevious(event.target.value ? Number(event.target.value) : null)}>
        <option value="">{t`Nobody (add the new manager only)`}</option>
        {card.managers.map(manager => <option key={manager.membership_id} value={manager.membership_id}>{manager.name || manager.email} · {manager.email}</option>)}
      </select>
    </Field>
    {previous !== null ? <fieldset className="grid gap-2">
      <legend className="mb-1 text-sm font-semibold text-ink">{t`What happens to the current manager`}</legend>
      {OUTCOMES.map(([value, label]) => <label key={value} className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="radio" name="previous-outcome" value={value} checked={outcome === value} onChange={() => setOutcome(value)} />{label}
      </label>)}
    </fieldset> : null}
    {needsRoles ? <fieldset className="grid gap-1 sm:grid-cols-2">
      <legend className="mb-1 text-sm font-semibold text-ink">{t`Roles they keep`}</legend>
      {STAFF_ROLES.map(([slug, label]) => <label key={slug} className="flex min-h-11 items-center gap-3 text-sm text-ink">
        <input type="checkbox" checked={roles.includes(slug)} onChange={() => toggle(slug)} />{label}
      </label>)}
    </fieldset> : null}
  </ActionDialog>;
}
