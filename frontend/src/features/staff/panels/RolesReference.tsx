import { plural, t } from "@lingui/core/macro";
import { ListRow, StatusPill } from "../../../components/ui";
import type { StaffRole } from "./rolesApi";
import { ROLE_DESCRIPTIONS } from "./roleSets";

/** Read-only list of the seven fixed roles. Roles are assigned per person, never created or edited. */
export function RolesReference({ roles, onShowHolders }: { roles: StaffRole[]; onShowHolders?: (slug: string) => void }) {
  return <section aria-labelledby="roles-heading" className="grid gap-3">
    <div>
      <h2 id="roles-heading" className="title-section">{t`Role definitions`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Every space has the same built-in roles. Space Manager and Member are held alone; the other roles combine, and a Machine Manager is limited to the machine types picked for that person.`}</p>
    </div>
    <div className="grid gap-2">
      {roles.map((role) => <ListRow key={role.id} title={role.name} identity={{ kind: "icon", icon: "User", tone: "accent" }}
        meta={ROLE_DESCRIPTIONS[role.slug] ?? role.granted_actions.join(", ")}
        right={<div className="flex flex-wrap items-center gap-2">
          <StatusPill label={role.exclusive ? t`Held alone` : t`Combines`} tone="neutral" />
          {/* PE3: "who holds" — the count opens the staff list filtered to this role. */}
          {onShowHolders && role.member_count ? <button type="button" className="desk-button min-h-11" onClick={() => onShowHolders(role.slug)}>{role.member_count === 1 ? t`Show 1 person` : t`Show ${role.member_count} people`}</button>
            : <StatusPill label={plural(role.member_count, { one: "# person", other: "# people" })} tone={role.member_count ? "info" : "neutral"} />}
        </div>} />)}
    </div>
  </section>;
}
