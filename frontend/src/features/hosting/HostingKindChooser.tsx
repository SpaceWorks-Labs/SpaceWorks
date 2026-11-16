import { t } from "@lingui/core/macro";
import type { HostingKind } from "./hostingApi";

const OPTIONS = (): Record<HostingKind, { title: string; detail: string }> => ({
  makerspace: { title: t`A makerspace`, detail: t`A workshop with tools and machines that members borrow and book.` },
  organization: { title: t`An organization`,
    detail: t`A club, society, chapter or company that runs events, memberships with ID cards and room bookings. No workshop needed.` },
});

/** Decision 295: what the applicant asks for. Shown only when the deployment offers more than one kind. */
export function HostingKindChooser({ kinds, value, onChange }: { kinds: HostingKind[]; value: HostingKind; onChange: (kind: HostingKind) => void }) {
  const options = OPTIONS();
  return <fieldset className="grid gap-2">
    <legend className="mb-1 text-sm font-semibold text-ink">{t`What do you want to set up?`}</legend>
    <div className="grid gap-3 sm:grid-cols-2">
      {kinds.map(kind => <label key={kind}
        className="flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-line bg-panel p-4 text-sm has-checked:border-accent has-checked:bg-accent-soft">
        <input type="radio" className="mt-1 h-5 w-5 shrink-0 accent-brand" name="requested_kind" value={kind}
          checked={value === kind} onChange={() => onChange(kind)} />
        <span className="grid gap-1"><span className="font-semibold text-ink">{options[kind].title}</span>
          <span className="text-muted">{options[kind].detail}</span></span>
      </label>)}
    </div>
  </fieldset>;
}
