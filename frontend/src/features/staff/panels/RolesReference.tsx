import { t } from "@lingui/core/macro";
import { ListRow, StatusPill } from "../../../components/ui";
import type { StaffRole } from "./rolesApi";
import { ROLE_DESCRIPTIONS } from "./roleSets";

/** Read-only list of the seven fixed roles. Roles are assigned per person, never created or edited. */
export function RolesReference({ roles }: { roles: StaffRole[] }) {
  return <section aria-labelledby="roles-heading" className="grid gap-3">
    <div>
      <h2 id="roles-heading" className="title-section">{t`Roles`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Every space has the same built-in roles. Space Manager and Member are held alone; the other roles combine, and a Machine Manager is limited to the machine types picked for that person.`}</p>
    </div>
    <div className="grid gap-2">
      {roles.map((role) => <ListRow key={role.id} title={role.name} identity={{ kind: "icon", icon: "User", tone: "accent" }}
        meta={ROLE_DESCRIPTIONS[role.slug] ?? role.granted_actions.join(", ")}
        right={<div className="flex flex-wrap items-center gap-2">
          <StatusPill label={role.exclusive ? t`Held alone` : t`Combines`} tone="neutral" />
          <StatusPill label={`${role.member_count} ${role.member_count === 1 ? "person" : "people"}`} tone={role.member_count ? "info" : "neutral"} />
        </div>} />)}
    </div>
  </section>;
}
